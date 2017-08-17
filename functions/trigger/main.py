# -*- coding: utf-8 -*-

from __future__ import print_function
from handler import TriggerHandler
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):

    handler = TriggerHandler(event)
    handler.run()