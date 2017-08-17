# -*- coding: utf-8 -*-

from __future__ import print_function
from libraries.lambda_handlers.trigger_handler import TriggerHandler


def handle(event, context):
    """
    Triggered by a cron job
    :param dict event:
    :param context:
    :return:
    """
    return TriggerHandler().handle(event, context)