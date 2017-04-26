# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the API
#

from __future__ import print_function
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler
from aws_tools.ses_handler import SESHandler
from catalog_handler import CatalogHandler

def handle(event, context):
    catalog = CatalogHandler(event, S3Handler, DynamoDBHandler, SESHandler)
    return catalog.handle_catalog()
