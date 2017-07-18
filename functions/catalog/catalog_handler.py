# -*- coding: utf-8 -*-

#
# Class for handling the Catalog
#

from __future__ import print_function

import os
import json
import tempfile
import copy
import time
from tools.file_utils import write_file
from tools.url_utils import get_url, url_exists
from tools.consistency_checker import ConsistencyChecker
from tools.dict_utils import read_dict
from d43_aws_tools import S3Handler, SESHandler, DynamoDBHandler


class CatalogHandler:
    API_VERSION = '3'

    resources_not_versified=['tw', 'tn', 'obs', 'ta', 'tq']

    def __init__(self, event, s3_handler=None, dynamodb_handler=None, ses_handler=None, consistency_checker=None, url_handler=None, url_exists_handler=None):
        """
        Initializes a catalog handler
        :param event: 
        :param s3_handler: This is passed in so it can be mocked for unit testing
        :param dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param ses_handler: This is passed in so it can be mocked for unit testing
        :param consistency_checker: This is passed in so it can be mocked for unit testing
        :param url_handler: This is passed in so it can be mocked for unit testing
        """
        self.cdn_url = read_dict(event, 'cdn_url').rstrip('/')
        self.cdn_bucket = read_dict(event, 'cdn_bucket')
        self.api_bucket = read_dict(event, 'api_bucket')
        self.api_url = read_dict(event, 'api_url').rstrip('/')
        self.to_email = read_dict(event, 'to_email')
        self.from_email = read_dict(event, 'from_email')

        if dynamodb_handler:
            self.progress_table = dynamodb_handler('d43-catalog-in-progress')
            self.status_table = dynamodb_handler('d43-catalog-status')
            self.errors_table = dynamodb_handler('d43-catalog-errors')
        else:
            self.progress_table = DynamoDBHandler('d43-catalog-in-progress')
            self.status_table = DynamoDBHandler('d43-catalog-status')
            self.errors_table = DynamoDBHandler('d43-catalog-errors')

        self.catalog = {
            "languages": []
        }
        if s3_handler:
            self.api_handler = s3_handler(self.api_bucket)
        else:
            self.api_handler = S3Handler(self.api_bucket)
        if ses_handler:
            self.ses_handler = ses_handler()
        else:
            self.ses_handler = SESHandler()
        if consistency_checker:
            self.checker = consistency_checker()
        else:
            self.checker = ConsistencyChecker()
        if not url_handler:
            self.get_url = get_url
        else:
            self.get_url = url_handler
        if not url_exists_handler:
            self.url_exists = url_exists
        else:
            self.url_exists = url_exists_handler

    def get_language(self, language):
        """
        Gets the existing language or creates a new one
        :param language: 
        :return: 
        """
        found_lang = None
        for lang in self.catalog['languages']:
            if lang['identifier'] == language['identifier']:
                found_lang = lang
                break
        if not found_lang:
            self.catalog['languages'].append(language)
        else:
            language = found_lang
        if 'resources' not in language:
            language['resources'] = []
        return language

    def handle_catalog(self):
        completed_items = 0
        items = self.progress_table.query_items()
        versification_package = None

        for item in items:
            repo_name = item['repo_name']
            try:
                package = json.loads(item['package'])
            except Exception as e:
                print('Skipping {}. Bad Manifest: {}'.format(repo_name, e))
                continue
            if repo_name == "catalogs":
                self.catalog['catalogs'] = package
            elif repo_name == 'localization':
                self._build_localization(package)
            elif repo_name == 'versification':
                versification_package = package
            else:
                if self._build_rc(item, package, self.checker):
                    completed_items += 1

        # process versification last
        if versification_package and not self._build_versification(versification_package, self.checker):
                # fail build if chunks are broken
                completed_items = 0

        # remove empty languages
        condensed_languages = []
        for lang in self.catalog['languages']:
            if 'resources' in lang and len(lang['resources']) > 0:
                condensed_languages.append(lang)
        self.catalog['languages'] = condensed_languages

        response = {
            'success': False,
            'incomplete': len(self.checker.all_errors) > 0,
            'message': None,
            'catalog': self.catalog
        }

        if completed_items > 0:
            if not self._catalog_has_changed(self.catalog):
                response['success'] = True
                response['message'] = 'No changes detected. Catalog not deployed'
                # publish the status if not already published
                if not self._read_status():
                    self._publish_status()
            else:
                cat_str = json.dumps(self.catalog, sort_keys=True)
                try:
                    catalog_path = os.path.join(tempfile.gettempdir(), 'catalog.json')
                    write_file(catalog_path, cat_str)
                    c_stats = os.stat(catalog_path)
                    print('New catalog built: {} Kilobytes'.format(c_stats.st_size * 0.001))

                    print('Uploading catalog.json to API')
                    self.api_handler.upload_file(catalog_path, 'v{0}/catalog.json'.format(self.API_VERSION), cache_time=0)
                    self._publish_status()

                    response['success'] = True
                    response['message'] = 'Uploaded new catalog to {0}/v{1}/catalog.json'.format(self.api_url, self.API_VERSION)
                except Exception as e:
                    self.checker.log_error('Unable to save catalog: {0}'.format(e))
        else:
            self.checker.log_error('There were no formats to process')

        self._handle_errors(self.checker)

        if not response['success']:
            response['catalog'] = None
            response['message'] = '{0}'.format(self.checker.all_errors)

        if(response['success']):
            print(response['message'])
        else:
            print('Catalog was not published due to errors')

        return response

    def _read_status(self):
        """
        Retrieves the recorded status of the catalog
        :return:
        """
        results = self.status_table.query_items({'api_version': self.API_VERSION})
        if not results:
            return None
        else:
            return results[0]

    def _publish_status(self, state='complete'):
        """
        Updates the catalog status
        :param state: the state of completion the catalog is in
        :return:
        """
        print('Recording catalog status')
        self.status_table.update_item(
            {'api_version': self.API_VERSION},
            {
                'state': state,
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'catalog_url': '{0}/v{1}/catalog.json'.format(self.api_url, self.API_VERSION)
            }
        )

    def _build_rc(self, item, manifest, checker):
        """
        Builds a RC entry in the catalog.
        :param item: 
        :param manifest: 
        :param checker: 
        :return: True if the entry was successfully added otherwise False
        """
        errors = checker.check(item)
        if errors:
            return False
        dc = manifest['dublin_core']
        language = dc['language']
        language = self.get_language(language)  # gets the existing language container or creates a new one

        formats = []
        for format in manifest['formats']:
            errors = checker.check_format(format, item)
            if not errors:
                formats.append(format)

        if len(formats) > 0:
            resource = copy.deepcopy(dc)
            resource['projects'] = []
            del resource['conformsto']
            del resource['format']
            del resource['language']
            del resource['type']
            resource['checking'] = copy.deepcopy(manifest['checking'])
            if not resource['relation']:
                resource['relation'] = []

            # store projects
            for project in manifest['projects']:
                if 'formats' in project:
                    for format in project['formats']:
                       checker.check_format(format, item)
                if not project['categories']:
                    project['categories'] = []
                del project['path']
                resource['projects'].append(project)

            # store formats
            # TRICKY: Bible usfm bundles should always be at the resource level
            is_bible = dc['identifier'] == 'ulb' or dc['identifier'] == 'udb'
            if len(manifest['projects']) == 1 and not (is_bible and self.has_usfm_bundle(formats)):
                # single-project RCs store formats in projects
                resource['projects'][0]['formats'] = formats
            else:
                # multi-project RCs store formats in resource
                resource['formats'] = formats

            if 'comment' not in resource: resource['comment'] = ''

            language['resources'].append(resource)
            return True

        return False

    def has_usfm_bundle(self, formats):
        """
        Checks if an array of formats contains a format that is a usfm bundle
        :param formats:
        :return:
        """
        for format in formats:
            if 'text/usfm' in format['format'] and 'type=bundle' in format['format']:
                return True
        return False

    def _build_versification(self, package, checker):
        """
        Adds versification chunks to projects in the catalog.
        Note: this may not do anything if no languages have been generated yet.
        self._build_rc will pick up the slack in that case.
        :param package: 
        :return: False if errors were encountered
        """
        dict = {}


        for project in package:
            dict[project['identifier']] = project
            if not self.url_exists(project['chunks_url']):
                checker.log_error('{} does not exist'.format(project['chunks_url']))
                # for performance's sake we'll fail on a single error
                return False

        # inject into existing projects
        for lang in self.catalog['languages']:
            if 'resources' not in lang: continue
            for res in lang['resources']:
                if 'projects' not in res: continue
                for proj in res['projects']:
                    if proj['identifier'] in dict and proj['versification']:
                        proj.update(dict[proj['identifier']])

        return True

    def _build_localization(self, package):
        """
        Adds localization to the catalog
        :param package: 
        :return: 
        """
        for lang in package:
            localization = package[lang]
            language = localization['language']
            del localization['language']
            language = self.get_language(language)  # gets the existing language container or creates a new one
            language.update(localization)

    def _catalog_has_changed(self, catalog):
        """
        Checks if the catalog has changed compared to the given catalog
        :param catalog:
        :return: 
        """
        try:
            catalog_url = '{0}/v{1}/catalog.json'.format(self.api_url, self.API_VERSION)
            current_catalog = json.loads(self.get_url(catalog_url, True))
            same = current_catalog == catalog
            return not same
        except Exception:
            return True

    def _handle_errors(self, checker):
        """
        Handles errors and warnings produced by the checker
        :param checker: 
        :return: 
        """
        if len(checker.all_errors) > 0:
            errors = self.errors_table.get_item({'id': 1})
            if errors:
                count = errors['count'] + 1
            else:
                count = 1
        else:
            count = 0

        self.errors_table.update_item({'id': 1}, {'count': count, 'errors': checker.all_errors})
        if count > 4:
            print("ALERT! FAILED MORE THAN 4 TIMES!")
            try:
                self.ses_handler.send_email(
                    Source=self.from_email,
                    Destination={
                        'ToAddresses': [
                            self.to_email
                        ]
                    },
                    Message={
                        'Subject': {
                            'Data': 'ERRORS Generating catalog.json',
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Text': {
                                'Data': 'Errors generating catalog.json: '+"\n"+"\n".join(checker.all_errors),
                                'Charset': 'UTF-8'
                            },
                            'Html': {
                                'Data': 'Errors generating catalog.json: <ul><li>'+'</li><li>'.join(checker.all_errors)+'</li></ul>',
                                'Charset': 'UTF-8'
                            }
                        }
                    }
                )
            except Exception as e:
                print("ALERT! FAILED TO SEND EMAIL: {}".format(e))