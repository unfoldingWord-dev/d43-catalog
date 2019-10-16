# -*- coding: utf-8 -*-

#
# Class for Resource Consistency test
#

from __future__ import print_function

import json
import logging
import urlparse

from libraries.tools.url_utils import url_exists


class ConsistencyChecker(object):

    def __init__(self, cdn_bucket, api_bucket, quiet=False):
        """

        :param cdn_bucket:
        :param api_bucket:
        :param quiet: log errors if set to false
        """
        self.cdn_bucket = cdn_bucket
        self.api_bucket = api_bucket
        self.quiet = quiet
        self.all_errors = []
        self.errors = []
        self.logger = logging.getLogger()

    def _url_is_local(self, url):
        """
        Checks if the url is from a local host
        :param url:
        :return:
        """
        url_info = urlparse.urlparse(url)
        return url_info.hostname in [self.cdn_bucket, self.api_bucket]

    def _url_exists(self, url):
        """
        This abstracts the external method `url_exists` into an instance method so that it can be mocked.
        It also ensures that url is not empty.
        :param url:
        :return:
        """
        return url and url_exists(url)

    def log_error(self, message):
        message = 'Consistency Check Failed: {}'.format(message)
        if not self.quiet:
            self.logger.error(message)
        self.errors.append(message)
        self.all_errors.append(message)

    def check(self, row):
        """
        Performs consistency checks on the row, language, and resource
        :param row: 
        :return: 
        """
        self.errors = []

        # checks the row
        if not row:
            self.log_error('None object given to consistency checker')
            return self.errors
        for key in ['repo_name', 'commit_id']:
            if key not in row:
                self.log_error('Row is missing key "{}"'.format(key))
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
            self.log_error('{0}: manifest missing key "{1}"'.format(repo_name, 'formats'))
        if not isinstance(manifest['formats'], list):
            self.log_error("{0}: manifest key formats must be an array".format(repo_name))

        return self.errors

    def _check_attributes(self, obj, keys, obj_name, repo_name):
        """
        Validates that the object contains the given keys.
        This will additionally validate the existence of url and signature
        :param obj:
        :param keys:
        :param obj_name:
        :param repo_name:
        :return:
        """
        if 'url' not in keys:
            keys.append('url')
        if 'signature' not in keys:
            keys.append('signature')

        # Check if the url is on our servers
        has_local_url = False
        if 'url' in obj and obj['url']:
            has_local_url = self._url_is_local(obj['url'])

        # validate keys exist
        for key in keys:
            if key not in obj:
                if key == 'signature' and not has_local_url:
                    # TRICKY: do not require signatures for remote urls
                    continue
                self.log_error("{0} container for '{1}' doesn't have '{2}'".format(obj_name, repo_name, key))

        # validate local urls exist
        if has_local_url and not self._url_exists(obj['url']):
            self.log_error("{0}: url '{1}' does not exist".format(repo_name, obj['url']))

        if has_local_url and not self._url_exists(obj['signature']):
            self.log_error("{0}: url '{1}' has not been signed yet".format(repo_name, obj['url']))

    def check_format(self, format, row):
        """
        Performs consistency checks on a format
        :return: 
        """
        self.errors = []

        repo_name = row['repo_name']

        self._check_attributes(format, ["format", "modified", "size", "url", "signature"], 'Format', repo_name)

        if 'chapters' in format and len(format['chapters']):
            # check format chapters
            for chapter in format['chapters']:
                self._check_format_chapter(chapter, row)

        return self.errors

    def _check_format_chapter(self, chapter, row):
        repo_name = row['repo_name']
        keys_to_check = ['size', 'length', 'modified', 'identifier', 'url', 'signature']
        self._check_attributes(chapter, keys_to_check, 'Format chapter', repo_name)

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
                raise Exception('manifest missing key "{0}"'.format(key))

        # check checking
        for key in ['checking_entity', 'checking_level']:
            if key not in manifest['checking']:
                raise Exception('manifest missing checking key "{0}"'.format(key))

        if not isinstance(manifest['checking']['checking_entity'], list):
            raise Exception('manifest key checking.checking_entity must be an array')

        # check projects
        if not isinstance(manifest['projects'], list):
            raise Exception('manifest key projects must be an array')

        for key in ['categories', 'identifier', 'path', 'sort', 'title', 'versification']:
            for project in manifest['projects']:
                if key not in project:
                    raise Exception('manifest missing project key "{0}"'.format(key))

        # check dublin_core
        for key in ['conformsto', 'contributor', 'creator', 'description', 'format', 'identifier', 'issued', 'language',
                    'modified', 'publisher', 'relation', 'rights', 'source', 'subject', 'title', 'type', 'version']:
            if key not in manifest['dublin_core']:
                raise Exception('manifest missing dublin_core key "{0}"'.format(key))

        expectedRCVersion = 'rc0.2'
        if manifest['dublin_core']['conformsto'].lower() != expectedRCVersion:
            raise Exception('unsupported rc version {}. Expected {}'.format(manifest['dublin_core']['conformsto'], expectedRCVersion))

        for key in ['direction', 'identifier', 'title']:
            if key not in manifest['dublin_core']['language']:
                raise Exception('manifest missing dublin_core.language key "{0}"'.format(key))

        if not isinstance(manifest['dublin_core']['source'], list):
            raise Exception('manifest key dublin_core.source must be an array')

        for key in ['version', 'identifier', 'language']:
            for source in manifest['dublin_core']['source']:
                if key not in source:
                    raise Exception('manifest missing dublin_core.source key "{0}"'.format(key))