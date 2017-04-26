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
        """
        Performs consistency checks on the row, language, and resource
        :param row: 
        :return: 
        """
        self.errors = []

        # checks the row
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
            manifest = json.loads(row['package'])
        except Exception as e:
            self.log_error('{0}: unable to decode "manifest" - {1}'.format(repo_name, e))
            return self.errors

        # check manifest
        try:
            ConsistencyChecker.check_manifest(manifest)
        except Exception as e:
            self.log_error('{0}: {1}'.format(repo_name, e))
            return self.errors

        # check formats
        if not 'formats' in manifest:
            self.log_error('{0}: manifest missing key - {1}'.format(repo_name, 'formats'))
        if not isinstance(manifest['formats'], list):
            self.log_error("{0}: manifest key formats must be an array".format(repo_name))

        return self.errors

    def check_format(self, format, row):
        """
        Performs consistency checks on a format
        :return: 
        """
        self.errors = []

        repo_name = row['repo_name']

        for key in ["format", "modified", "size", "url", "signature"]:
            if key not in format:
                self.log_error("Format container for '{0}' doesn't have '{1}'".format(repo_name, key))
        if 'url' not in format or 'signature' not in format:
            return self.errors
        if not self.url_exists(format['url']):
            self.log_error("{0}: {1} does not exist".format(repo_name, format['url']))
        if not format['signature']:
            self.log_error("{0}: {1} has not been signed yet".format(repo_name, format['url']))
        elif not self.url_exists(format['signature']):
            self.log_error("{0}: {1} does not exist".format(repo_name, format['signature']))

        return self.errors

    @staticmethod
    def check_manifest(manifest):
        """
        Checks the manifest for consistency with the RC0.2 spec
        An exception is raised if any inconsistency is found
        :param manifest: 
        :return: 
        """
        if not manifest:
            raise Exception('manifest is null')

        for key in ['dublin_core', 'checking', 'projects']:
            if key not in manifest:
                raise Exception('manifest missing key - {0}'.format(key))

        # check checking
        for key in ['checking_entity', 'checking_level']:
            if key not in manifest['checking']:
                raise Exception('manifest missing checking key - {0}'.format(key))

        if not isinstance(manifest['checking']['checking_entity'], list):
            raise Exception('manifest key checking.checking_entity must be an array')

        # check projects
        if not isinstance(manifest['projects'], list):
            raise Exception('manifest key projects must be an array')

        for key in ['categories', 'identifier', 'path', 'sort', 'title', 'versification']:
            for project in manifest['projects']:
                if key not in project:
                    raise Exception('manifest missing project key - {0}'.format(key))

        # check dublin_core
        for key in ['conformsto', 'contributor', 'creator', 'description', 'format', 'identifier', 'issued', 'language',
                    'modified', 'publisher', 'relation', 'rights', 'source', 'subject', 'title', 'type', 'version']:
            if key not in manifest['dublin_core']:
                raise Exception('manifest missing dublin_core key - {0}'.format(key))

        for key in ['direction', 'identifier', 'title']:
            if key not in manifest['dublin_core']['language']:
                raise Exception('manifest missing dublin_core.language key - {0}'.format(key))

        if not isinstance(manifest['dublin_core']['source'], list):
            raise Exception('manifest key dublin_core.source must be an array')

        for key in ['version', 'identifier', 'language']:
            for source in manifest['dublin_core']['source']:
                if key not in source:
                    raise Exception('manifest missing dublin_core.source key - {0}'.format(key))