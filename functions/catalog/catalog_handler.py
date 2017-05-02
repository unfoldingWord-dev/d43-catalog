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

from general_tools.file_utils import write_file
from general_tools.url_utils import get_url
from tools.consistency_checker import ConsistencyChecker

class CatalogHandler:
    API_VERSION = 3

    def __init__(self, event, s3_handler, dynamodb_handler, ses_handler):
        """
        Initializes a catalog handler
        :param event: 
        :param s3_handler: This is passed in so it can be mocked for unit testing
        :param dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param ses_handler: This is passed in so it can be mocked for unit testing
        """
        self.api_bucket = self.retrieve(event, 'api_bucket')
        self.to_email = self.retrieve(event, 'to_email')
        self.from_email = self.retrieve(event, 'from_email')

        self.progress_table = dynamodb_handler('d43-catalog-in-progress')
        self.production_table = dynamodb_handler('d43-catalog-production')
        self.errors_table = dynamodb_handler('d43-catalog-errors')
        self.catalog = {
            "languages": []
        }
        self.api_handler = s3_handler(self.api_bucket)
        self.ses_handler = ses_handler()
        self.versification_package = None

    def get_language(self, language):
        """
        Gets the existing language container or creates a new one
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

    def get_project(self, language, project):
        """
        Gets the existing project from the language or creates a new one
        :param language: 
        :param project: 
        :return: 
        """
        found_proj = None
        if 'projects' not in language:
            language['projects'] = []

        for proj in language['projects']:
            if proj['identifier'] == project['identifier']:
                found_proj = proj
                break
        if not found_proj:
            language['projects'].append(project)
        else:
            project = found_proj
        return project


    @staticmethod
    def retrieve(dictionary, key, dict_name=None):
        """
        Retrieves a value from a dictionary, raising an error message if the
        specified key is not valid
        :param dict dictionary:
        :param any key:
        :param str|unicode dict_name: name of dictionary, for error message
        :return: value corresponding to key
        """
        if key in dictionary:
            return dictionary[key]
        dict_name = "dictionary" if dict_name is None else dict_name
        raise Exception('{k} not found in {d}'.format(k=repr(key), d=dict_name))

    def handle_catalog(self):
        completed_items = 0
        items = self.progress_table.query_items()
        checker = ConsistencyChecker()

        for item in items:
            repo_name = item['repo_name']
            try:
                manifest = json.loads(item['package'])
            except Exception as e:
                print('Skipping {}. Bad Manifest: {}'.format(repo_name, e))
                continue
            if repo_name == "catalogs":
                self.catalog['catalogs'] = manifest
            elif repo_name == 'localization':
                self._build_localization(manifest)
            elif repo_name == 'versification':
                if not self._build_versification(manifest, checker):
                    # fail build if chunks are broken
                    completed_items = 0
                    break
            else:
                if self._build_rc(item, manifest, checker):
                    completed_items += 1

        # remove empty languages
        condensed_languages = []
        for lang in self.catalog['languages']:
            if 'resources' in lang and len(lang['resources']) > 0:
                condensed_languages.append(lang)
        self.catalog['languages'] = condensed_languages

        response = {
            'success': False,
            'incomplete': len(checker.all_errors) > 0,
            'message': None,
            'catalog': self.catalog
        }

        if completed_items > 0:
            if not self._catalog_has_changed(self.catalog):
                response['success'] = True
                response['message'] = 'No changes detected. Catalog not deployed'
            else:
                data = {
                    'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    'catalog': json.dumps(self.catalog, sort_keys=True)
                }
                try:
                    self.production_table.insert_item(data)
                    catalog_path = os.path.join(tempfile.gettempdir(), 'catalog.json')
                    write_file(catalog_path, self.catalog)
                    self.api_handler.upload_file(catalog_path, 'v{0}/catalog.json'.format(self.API_VERSION), cache_time=0)

                    response['success'] = True
                    response['message'] = 'Uploaded new catalog to https://{0}/v{1}/catalog.json'.format(self.api_bucket, self.API_VERSION)
                except Exception as e:
                    checker.log_error('Unable to save catalog.json: {0}'.format(e))
        else:
            checker.log_error('There were no formats to process')

        self._handle_errors(checker)

        if not response['success']:
            response['catalog'] = None
            response['message'] = '{0}'.format(checker.all_errors)

        if(response['success']):
            print(response['message'])
        else:
            print('Catalog was not published due to errors')

        return response

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
            if not resource['relation']:
                resource['relation'] = []

            # store projects
            for project in manifest['projects']:
                if not project['categories']:
                    project['categories'] = []
                del project['path']
                resource['projects'].append(project)

                # add versification chunks
                if self.versification_package and project['identifier'] in self.versification_package:
                    project.update(self.versification_package[project['identifier']])

            # store formats
            if len(manifest['projects']) == 1:
                # single-project RCs store formats in projects
                resource['projects'][0]['formats'] = formats
            else:
                # multi-project RCs store formats in resource
                resource['formats'] = formats

            language['resources'].append(resource)
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
        # remember for use in self._build_rc
        self.versification_package = package

        for project in package:
            if not ConsistencyChecker.url_exists(project['chunks_url']):
                checker.log_error('{} does not exist'.format(project['chunks_url']))
                # for performance's sake we'll fail on a single error
                return False

        # inject into existing projects
        for lang in self.catalog['languages']:
            for project in package:
                versification = project['chunks_url']
                project = self.get_project(lang, project)
                project['chunks_url'] = versification

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
            catalog_url = 'https://{0}/v{1}/catalog.json'.format(self.api_bucket, self.API_VERSION)
            current_catalog = json.loads(get_url(catalog_url, True))
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