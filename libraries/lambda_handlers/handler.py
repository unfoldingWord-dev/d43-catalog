from __future__ import unicode_literals, print_function
import json
import logging
from abc import ABCMeta, abstractmethod


class Handler(object):
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
        else:
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

    def run(self, **kwargs):
        """
        :param kwargs:
        :return dict:
        """
        self.logger.debug("EVENT:")
        self.logger.debug(json.dumps(self.event))
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