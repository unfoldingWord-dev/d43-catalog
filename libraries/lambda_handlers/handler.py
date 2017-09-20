from __future__ import unicode_literals, print_function
import json
import logging
import sys

from abc import ABCMeta, abstractmethod
from libraries.tools.error_reporter import ErrorReporter


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
        to_email = self.__find_stage_var('to_email', event)
        from_email = self.__find_stage_var('from_email', event)

        # set up error reporter
        lambda_name = self.__class__.__name__
        if self.context:
            lambda_name = self.context.function_name
        table_name = '{}d43-catalog-errors'.format(self.stage_prefix())
        self.reporter = ErrorReporter(reporter=lambda_name,
                                      table=table_name,
                                      request_id=self.aws_request_id,
                                      to_email=to_email,
                                      from_email=from_email,
                                      error_threshold=8)

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

    def report_error(self, message):
        """
        Records an error that will be reported to administrators if not automatically resolved.
        :param string|list message: the error message
        :return:
        """
        self.reporter.add_error(message)

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
            self.reporter.commit()

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
