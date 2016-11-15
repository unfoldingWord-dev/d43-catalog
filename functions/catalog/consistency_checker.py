# -*- coding: utf-8 -*-

#
# Class for Resource Consistency test
#

from __future__ import print_function

import json
import httplib
from urlparse import urlparse


class ConsistencyChecker(object):

    def __init__(self, quiet=False):
        self.quiet = quiet
        self.all_errors = []
        self.errors = []

    def log_error(self, message):
        if not self.quiet:
            print(message)
        self.errors.append(message)
        self.all_errors.append(message)

    @staticmethod
    def url_exists(url):
        p = urlparse(url)
        conn = httplib.HTTPConnection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
        return resp.status == 301 or resp.status == 200

    def check(self, row):
        self.errors = []

        if not row or 'repo_name' not in row or 'commit_id' not in row:
            self.log_error('Bad row in table')
            return self.errors

        repo_name = row['repo_name']
        commit_id = row['commit_id']

        if not repo_name:
            self.log_error('Empty repo_name in table')
            return self.errors

        if not commit_id:
            self.log_error("{0}: empty 'commit_id'".format(repo_name))
            return self.errors

        if 'package' not in row or not row['package']:
            self.log_error("{0}: 'package' not found".format(repo_name))
            return self.errors

        try:
            package = json.loads(row['package'])
        except Exception as e:
            self.log_error('{0}: unable to decode "package" - {1}'.format(repo_name, e))
            return self.errors

        if 'language' not in package or 'slug' not in package['language']:
            self.log_error("{0}: 'language' is not set up properly".format(repo_name))
            return self.errors

        if 'resource' not in package or 'slug' not in package['resource']:
            self.log_error("{0}: 'resource' is not set up properly".format(repo_name))
            return self.errors

        resource = package['resource']

        for key in ['name', 'icon', 'status', 'formats']:
            if key not in resource:
                self.log_error("{0}: '{1}' does not exist".format(repo_name, key))
                return self.errors

        if not isinstance(resource['formats'], list):
            self.log_error("{0}: 'formats' is not an array".format(repo_name))

        for format in resource['formats']:
            for key in ["mime_type", "modified_at", "size", "url", "sig"]:
                if key not in format:
                    self.log_error("Format container for '{0}' doesn't have '{1}'".format(repo_name, key))
            if 'url' not in format or 'sig' not in format:
                continue
            if not self.url_exists(format['url']):
                self.log_error("{0}: {1} does not exist".format(repo_name, format['url']))
            if not format['sig']:
                self.log_error("{0}: {1} has not been signed yet".format(repo_name, format['url']))
            elif not self.url_exists(format['sig']):
                self.log_error("{0}: {1} does not exist".format(repo_name, format['sig']))

        return self.errors
