from __future__ import unicode_literals, print_function
import json
import arrow
import logging
import sys
from abc import ABCMeta, abstractmethod
from d43_aws_tools import DynamoDBHandler, SESHandler

class Handler(object):
    """
    Provides a base for lambda handlers
    """
    __metaclass__ = ABCMeta

    # The number of consecutive lambda instances that must report errors before an email is sent
    __ERROR_THRESHOLD = 4

    def __init__(self, event, context):
        """

        :param dict event:
        :param context:
        """

        # Make Boto3 not be so noisy
        logging.getLogger('boto3').setLevel(logging.ERROR)
        logging.getLogger('botocore').setLevel(logging.ERROR)

        # Make USFM-tools not be so noisy
        logging.getLogger('usfm_tools').setLevel(logging.WARNING)

        # Set up logger
        self.logger = logging.getLogger() # type: logging._loggerClass
        self.logger.setLevel(logging.DEBUG)
        self.event = event
        self.context = context
        self.__num_error_reporters = 0

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
        log_level = self.__find_stage_var('log_level', event)
        if log_level:
            self.__set_logging_level(log_level)

        # get emails
        self.to_email = self.__find_stage_var('to_email', event)
        self.from_email = self.__find_stage_var('from_email', event)

    def __find_stage_var(self, key, dict):
        """
        Searches for a stage variable in the dictionary.
        The key may exist in 'stage-variables' or in the root of the dictionary
        :param key:
        :param dict:
        :return:
        """
        if not dict:
            return None
        if 'stage-variables' in dict and key in dict['stage-variables']:
            return dict['stage-variables'][key]
        elif key in dict:
            return dict[key]
        else:
            return None


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

    def sanitize_identifier(self, identifier, lower=True):
        """
        Sanitizes an identifier.
        Warnings will be produced if the identifier is malformed
        :param string identifier:
        :param bool lower: returns the identifier in lower case
        :return:
        """
        # errors
        if not isinstance(identifier, basestring):
            self.logger.error('Identifier "{}" is not a string'.format(identifier))
            return identifier
        if not identifier.strip():
            self.logger.error('Identifier "{}" is empty'.format(identifier))
            return identifier

        # warnings
        if '_' in identifier:
            self.logger.warning('Identifier "{}" contains an underscore'.format(identifier))

        if lower:
            return identifier.strip().lower()
        else:
            return identifier.strip()


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

    def clear_errors(self):
        """
        Empties the error queue
        :return:
        """
        lambda_name = self.__class__.__name__
        if self.context:
            lambda_name = self.context.function_name
        db = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix()))
        db.delete_item({'lambda': lambda_name})

    def report_error(self, message):
        """
        Records an error that will be reported to administrators if not automatically resolved.
        :param string|list message: the error message
        :return:
        """
        if isinstance(message, list):
            self.logger.info('Reporting Error: {}'.format(json.dumps(message)), exc_info=1)
        elif isinstance(message, str):
            self.logger.info('Reporting Error: {}'.format(message), exc_info=1)
        else:
            self.logger.warning('Unable to report error. Invalid type "{}"'.format(type(message)), exc_info=1)
            return

        lambda_name = self.__class__.__name__
        if self.context:
            lambda_name = self.context.function_name

        # load existing report
        db = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix()))
        item = db.get_item({'lambda': lambda_name})
        if not item:
            item = {}
        report = {
            'errors': [],
            'lambda': lambda_name,
            'reporters': []
        }
        report.update(item)

        # start new report
        if self.aws_request_id not in report['reporters']:
            report['errors'] = []
            report['reporters'].append(self.aws_request_id)

        # append errors
        if isinstance(message, list):
            timestamp = arrow.utcnow().isoformat()
            for m in message:
                report['errors'].append({
                    'message': m.decode('utf-8'),
                    'timestamp': timestamp
                })
        else:
            report['errors'].append({
                'message': message.decode('utf-8'),
                'timestamp': arrow.utcnow().isoformat()
            })

        self.__num_error_reporters = len(report['reporters'])

        # TODO: cache the report and update after lambda is finished

        # update error report
        db.update_item({'lambda': lambda_name}, report)

    def __email_error_report(self, to_email, from_email):
        """
        Emails the error report.
        :param to_email:
        :param from_email:
        :return:
        """
        # get reporter name
        lambda_name = self.__class__.__name__
        if self.context:
            lambda_name = self.context.function_name

        # TODO: send from cache

        # get errors
        db = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix()))
        report = db.get_item({'lambda': lambda_name})
        if report and 'errors' in report:
            errors = report['errors']
        else:
            errors = []

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
            self.logger.error('Failed to report errors {}'.format(e.message), exc_info=1)

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
            raise Exception, EnvironmentError('Bad Request: {}'.format(e.message)), sys.exc_info()[2]
        finally:
            if self.__num_error_reporters >= self.__ERROR_THRESHOLD:
                self.__email_error_report(self.to_email, self.from_email)

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