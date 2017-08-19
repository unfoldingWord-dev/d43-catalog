from libraries.lambda_handlers.handler import Handler
import grequests
from functools import partial
import json

from libraries.tools.lambda_utils import is_lambda_running, set_lambda_running


class TriggerHandler(Handler):
    """
    Triggers necessary lambda functions in the catalog pipeline.

    This setup allows the functions to use the same set of
    stage variables from the API gateway.
    """

    def __init__(self, event, context, **kwargs):
        super(TriggerHandler, self).__init__(event, context)
        if 'logger' in kwargs:
            self.logger = kwargs['logger']

        self.api_url = self.retrieve(self.event, 'api_url').rstrip('/')
        self.api_version = self.retrieve(self.event, 'api_version')

    def _run(self, **kwargs):
        """
        :param kwargs:
        :return:
        """
        running_db_name = '{}d43-catalog-running'.format(self.stage_prefix())
        if is_lambda_running(self.context, running_db_name):
            self.logger.info('Lambda is already running. Aborting execution.')
            return False
        else:
            set_lambda_running(self.context, running_db_name)

        urls = [
            'catalog',
            'fork',
            'signing',
            'ts-v2-catalog',
            'uw-v2-catalog'
        ]
        requests = []
        for u in urls:
            lambda_url = '{}/v{}/lambda/{}'.format(self.api_url, self.api_version, u)
            self.logger.info('Triggering {}'.format(lambda_url))
            requests.append(grequests.request('GET', lambda_url, callback=partial(self.__callback, self.logger)))

        grequests.imap(requests, exception_handler=self.__exception_handler)

    @staticmethod
    def __exception_handler(request, exception):
        print('Failed to trigger {}. {}'.format(request.url, exception.message))

    @staticmethod
    def __callback(logger, response, **kwargs):
        if response.status_code >= 300:
            # check for auth errors
            logger.warning('Unexpected response for {}: {}'.format(response.url, response.text))
        else:
            try:
                data = json.loads(response.text)
                if 'errorMessage' in data:
                    logger.warning('Unexpected response for {}: {}'.format(response.url, data['errorMessage']))
            except:
                pass
