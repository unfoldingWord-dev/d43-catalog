from libraries.lambda_handlers.handler import Handler
import grequests
from functools import partial
import json


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

    def _run(self, **kwargs):
        """
        :param kwargs:
        :return:
        """
        api_url = self.retrieve(self.event, 'api_url')

        urls = [
            'catalog',
            'fork',
            'signing',
            'ts-v2-catalog',
            'uw-v2-catalog'
        ]
        requests = []
        for u in urls:
            lambda_url = '{}/{}'.format(api_url, u)
            self.logger.info('Triggering {}'.format(lambda_url))
            requests.append(grequests.request('GET', lambda_url, callback=partial(self.__callback, self.logger)))

        grequests.map(requests, exception_handler=self.__exception_handler)

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
