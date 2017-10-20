# -*- coding: utf-8 -*-

#
# Lambda function to handle displaying the pipeline status
#

from libraries.lambda_handlers.status_handler import StatusHandler

def handle(event, context):
    handler = StatusHandler(event, context)
    return handler.run()
