import grequests
from tools.dict_utils import read_dict
import logging
from functools import partial
import json

"""
This lambda function is used to trigger other necessary functions.
A cron job will execute this function on a schedule to trigger configured
functions.

This setup allows all of the configured functions to receive
stage variables from the API gateway so that variables
can be managed from a single location.
"""

class TriggerHandler:

    def __init__(self, event, logger_handler=None):
        self.api_url = read_dict(event, 'api_url', 'Environment Vars').rstrip('/')

        if logger_handler:
            self.logger = logger_handler
        else:
            self.logger = logging.getLogger()

    def run(self):
        urls = [
            'catalog',
            'fork',
            'signing',
            'ts-v2-catalog',
            'uw-v2-catalog'
        ]
        requests = []
        for u in urls:
            lambda_url = '{}/{}'.format(self.api_url, u)
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
