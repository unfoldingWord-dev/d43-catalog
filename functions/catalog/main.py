# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the API
#

from __future__ import print_function
from catalog_handler import CatalogHandler

def handle(event, context):
    catalog = CatalogHandler(event)
    return catalog.handle_catalog()
