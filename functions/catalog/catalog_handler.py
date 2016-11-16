# -*- coding: utf-8 -*-

#
# Class for handling the Catalog
#

from __future__ import print_function

import os
import json
import tempfile
import time

from general_tools.file_utils import write_file
from general_tools.url_utils import get_url
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler
from aws_tools.ses_handler import SESHandler
from consistency_checker import ConsistencyChecker


class CatalogHandler:
    API_VERSION = 3

    def __init__(self, event):
        self.api_bucket = self.retrieve(event, 'api_bucket')
        self.to_email = self.retrieve(event, 'to_email')
        self.from_email = self.retrieve(event, 'from_email')

        self.progress_table = DynamoDBHandler('d43-catalog-in-progress')
        self.production_table = DynamoDBHandler('d43-catalog-production')
        self.errors_table = DynamoDBHandler('d43-catalog-errors')
        self.catalog = {
            "languages": []
        }
        self.api_handler = S3Handler(self.api_bucket)
        self.ses_handler = SESHandler()

    # gets the existing language container or creates a new one
    def get_language(self, language):
        found_lang = None
        for lang in self.catalog['languages']:
            if lang['slug'] == language['slug']:
                found_lang = lang
        if not found_lang:
            self.catalog['languages'].append(language)
        else:
            language = found_lang
        return language

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
        items = self.progress_table.query_items()
        checker = ConsistencyChecker()

        for item in items:
            repo_name = item['repo_name']
            package = json.loads(item['package'])
            if repo_name == "catalogs":
                self.catalog['catalogs'] = package
            elif repo_name == 'localization':
                for lang in package:
                    localization = package[lang]
                    language = localization['language']
                    del localization['language']
                    language = self.get_language(language)  # gets the existing language container or creates a new one
                    language.update(localization)
            else:
                errors = checker.check(item)
                if not errors:
                    language = package['language']
                    language = self.get_language(language)  # gets the existing language container or creates a new one
                    if 'resources' not in language:
                        language['resources'] = []
                    language['resources'].append(package['resource'])

        if not checker.all_errors:
            try:
                catalog_url = 'https://{0}/v{1}/catalog.json'.format(self.api_bucket, self.API_VERSION)
                current_catalog = json.loads(get_url(catalog_url, True))
                if self.catalog == current_catalog:
                    return {
                        'success': True,
                        'message': 'No changes in the catalog'
                    }
            except Exception:
                pass

            data = {
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'catalog': json.dumps(self.catalog, sort_keys=True)
            }
            try:
                self.production_table.insert_item(data)
                catalog_path = os.path.join(tempfile.gettempdir(), 'catalog.json')
                write_file(catalog_path, self.catalog)
                self.api_handler.upload_file(catalog_path, 'v{0}/catalog.json'.format(self.API_VERSION), cache_time=0)
                return {
                    'success': True,
                    'message': 'Uploaded new catalog to https://{0}/v{1}/catalog.json'.format(self.api_bucket, self.API_VERSION)
                }
            except Exception as e:
                checker.log_error('Unable to save catalog.json: {0}'.format(e))

        if checker.all_errors:
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
            response = self.ses_handler.send_email(
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

        return {
            'success': False,
            'message': '{0}'.format(checker.all_errors)
        }
