# Method for handling the registration of conversion modules

from __future__ import print_function

from acceptance_test import AcceptanceTest


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

        acceptance = AcceptanceTest(url)
        acceptance.run()
        print(acceptance.errors)
        return acceptance.errors
