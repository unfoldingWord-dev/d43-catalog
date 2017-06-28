# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the uW v2 API
#

from __future__ import print_function
from d43_aws_tools import DynamoDBHandler, S3Handler, SESHandler
from uw_v2_catalog_handler import UwV2CatalogHandler

def handle(event, context):
    try:
        catalog = UwV2CatalogHandler(event, S3Handler, DynamoDBHandler, SESHandler)
        return catalog.convert_catalog()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
