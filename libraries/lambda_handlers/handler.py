from __future__ import unicode_literals, print_function
import json
import arrow
import logging
from abc import ABCMeta, abstractmethod
from d43_aws_tools import DynamoDBHandler, SESHandler

class Handler(object):
    """
    Provides a base for lambda handlers
    """
    __metaclass__ = ABCMeta

    def __init__(self, event, context):
        """

        :param dict event:
        :param context:
        """

        # Make Boto3 not be so noisy
        logging.getLogger('boto3').setLevel(logging.ERROR)
        logging.getLogger('botocore').setLevel(logging.ERROR)

        # Set up logger
        self.logger = logging.getLogger() # type: logging._loggerClass
        self.logger.setLevel(logging.DEBUG)
        self.event = event
        self.context = context

        # get stage name
        if event and 'context' in event and 'stage' in event['context']:
            self.aws_stage = event['context']['stage']
        elif event and 'stage' in event:
            # TRICKY: the stage must be manually given for cloudwatch events
            self.aws_stage = event['stage']
        else:
            self.logger.warning('AWS Stage is not specified.')
            self.aws_stage = None

        # get request id
        if context:
            self.aws_request_id = context.aws_request_id
        else:
            self.aws_request_id = None

        # get logging level
        if event and 'log_level' in event:
            self.__set_logging_level(event['log_level'])
        elif event and 'stage-variables' in event and 'log_level' in event['stage-variables']:
            self.__set_logging_level(event['stage-variables']['log_level'])

    def __set_logging_level(self, level):
        """
        Sets the logging level of the global logger
        :param level:
        :return:
        """
        level = level.lower()
        if level == 'info':
            self.logger.setLevel(logging.INFO)
        elif level == 'warning':
            self.logger.setLevel(logging.WARNING)
        elif level == 'error':
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.setLevel(logging.DEBUG)

    def stage_prefix(self):
        """
        Returns the prefix that should be used for operations within this stage. e.g. database names etc.
        The prefix for an undefined or production stages will be an empty string.
        :return:
        """
        if self.aws_stage and not self.aws_stage.lower().startswith('prod'):
            return '{}-'.format(self.aws_stage.lower())
        else:
            return ''

    def report_error(self, message, to_email=None, from_email=None, queue_size=4):
        """
        Submits an error report to administrators
        :param string|list message: the error message
        :param int queue_size: The number of error reports to store in the queue. An email is sent when the queue is full
        :return:
        """
        if isinstance(message, list):
            self.logger.info('Reporting Error: {}'.format(json.dumps(message)))
        elif isinstance(message, str):
            self.logger.info('Reporting Error: {}'.format(message))
        else:
            self.logger.warning('Unable to report error. Invalid type "{}"'.format(type(message)))
            return

        lambda_name = self.__class__.__name__
        if self.context:
            lambda_name = self.context.function_name

        # check existing errors
        db = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix()))
        report = db.get_item({'lambda': lambda_name})
        if report and 'errors' in report:
            errors = report['errors']
            count = report['count']
        else:
            errors = []
            count = 0

        # append errors
        if isinstance(message, list):
            timestamp = arrow.utcnow().isoformat()
            for m in message:
                errors.append({
                    'message': m,
                    'timestamp': timestamp
                })
        else:
            errors.append({
                'message': message,
                'timestamp': arrow.utcnow().isoformat()
            })

        # record errors
        db.update_item({'lambda': lambda_name}, {
            'count': count + 1, # increment count every time this method is called
            'errors': errors
        })

        # send report
        if count >= queue_size and to_email and from_email:
            # send message
            self.logger.info('Emailing error report')
            text = ''
            html = ''
            for e in errors:
                text += '----------------\n{}\n{}'.format(e['timestamp'], e['message'])
                html += '<li><i>{}</i>: {}</li>'.format(e['timestamp'], e['message'])
            ses = SESHandler()
            try:
                ses.send_email(
                    Source=from_email,
                    Destination={
                        'ToAddresses': [
                            to_email
                        ]
                    },
                    Message={
                        'Subject': {
                            'Data': 'ERRORS running {}'.format(lambda_name),
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Text': {
                                'Data': 'Errors running {}\n\n{}'.format(lambda_name, text),
                                'Charset': 'UTF-8'
                            },
                            'Html': {
                                'Data': 'Errors running {}\n\n<ul>{}</ul>'.format(lambda_name, html)
                            }
                        }
                    }
                )
                # clear error queue
                db.delete_item({'lambda': lambda_name})
            except Exception as e:
                self.logger.error('Failed to report errors {}'.format(e.message))

    def run(self, **kwargs):
        """
        :param kwargs:
        :return dict:
        """
        self.logger.debug("EVENT:")
        self.logger.debug(json.dumps(self.event))
        self.logger.debug('Stage Prefix: {}'.format(self.stage_prefix()))
        try:
            return self._run(**kwargs)
        except Exception as e:
            self.logger.error(e.message, exc_info=1)
            raise EnvironmentError('Bad Request: {}'.format(e.message))

    @abstractmethod
    def _run(self, **kwargs):
        """
        Dummy function for handlers.

        Override this so handle() will catch the exception and make it a "Bad Request: "

        :param dict event:
        :param context:
        :param kwargs:
        :return dict:
        """
        raise NotImplementedError()

    @staticmethod
    def retrieve(dictionary, key, dict_name=None):
        """
        Retrieves a value from a dictionary.

        raises an error message if the specified key is not valid

        :param dict dictionary:
        :param any key:
        :param str|unicode dict_name: name of dictionary, for error message
        :return: value corresponding to key
        """
        if key in dictionary:
            return dictionary[key]
        dict_name = "dictionary" if dict_name is None else dict_name
        raise Exception('\'{k}\' not found in {d}'.format(k=key, d=dict_name))