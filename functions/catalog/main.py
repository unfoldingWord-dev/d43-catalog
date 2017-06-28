# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the API
#

from __future__ import print_function
from d43_aws_tools import DynamoDBHandler, S3Handler, SESHandler
from catalog_handler import CatalogHandler

def handle(event, context):
    try:
        catalog = CatalogHandler(event=event, s3_handler=S3Handler, dynamodb_handler=DynamoDBHandler, ses_handler=SESHandler)
        return catalog.handle_catalog()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
