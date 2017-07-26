# Method for handling the registration of conversion modules

from __future__ import print_function

import httplib

from acceptance_test import AcceptanceTest
from d43_aws_tools import SESHandler
from tools.url_utils import get_url


class URLHandler(object):
    """
    TRICKY: we wrap get_url so we can mock it for unit testing
    """
    def get_url(self, url, catch_exception=False):
        return get_url(url, catch_exception)


def handle(event, context):
    # this shouldn't happen, but just in case
    if 'Records' not in event:
        return False
    for record in event['Records']:
        # check if this is S3 bucket record
        if 's3' not in record:
            return False
        bucket_name = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        url = 'https://{0}/{1}'.format(bucket_name, key)

        acceptance = AcceptanceTest(url, URLHandler, httplib.HTTPConnection, SESHandler, to_email="acceptancetest@door43.org", from_email="acceptancetest@door43.org")
        acceptance.run()
        print(acceptance.errors)
        return acceptance.errors
