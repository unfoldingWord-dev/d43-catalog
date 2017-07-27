# -*- coding: utf-8 -*-

#
# Lambda function for generating the catalog.json file for the API
#

from __future__ import print_function
from catalog_handler import CatalogHandler
from tools.file_utils import wipe_temp

def handle(event, context):
    wipe_temp(ignore_errors=True)
    try:
        catalog = CatalogHandler(event=event)
        return catalog.handle_catalog()
    except Exception as e:
        raise Exception('Bad Request: {0}'.format(e))
