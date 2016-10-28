# -*- coding: utf-8 -*-

#
# Webhook client for updating the catalog
#

from __future__ import print_function

from repo_handler import RepoHandler


def handle(event, context):
#    try:
        RepoHandler(event).run()
#   except Exception as e:
#       raise Exception('Bad Request: {0}'.format(e))

