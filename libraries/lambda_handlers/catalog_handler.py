# -*- coding: utf-8 -*-
from __future__ import print_function

import copy
import json
import os
import tempfile
import time

from libraries.lambda_handlers.instance_handler import InstanceHandler
from d43_aws_tools import S3Handler, SESHandler, DynamoDBHandler
from libraries.tools.consistency_checker import ConsistencyChecker
from libraries.tools.file_utils import write_file
from libraries.tools.url_utils import get_url, url_exists

class CatalogHandler(InstanceHandler):

    def __init__(self, event, context, **kwargs):
        super(CatalogHandler, self).__init__(event, context)

        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url').rstrip('/')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket')
        self.api_bucket = self.retrieve(env_vars, 'api_bucket')
        self.api_url = self.retrieve(env_vars, 'api_url').rstrip('/')
        self.to_email = self.retrieve(env_vars, 'to_email')
        self.from_email = self.retrieve(env_vars, 'from_email')
        self.api_version = self.retrieve(env_vars, 'version')

        if 'dynamodb_handler' in kwargs:
            db_handler = kwargs['dynamodb_handler']
            self.progress_table = db_handler('{}d43-catalog-in-progress'.format(self.stage_prefix()))
            self.status_table = db_handler('{}d43-catalog-status'.format(self.stage_prefix()))
            self.errors_table = db_handler('{}d43-catalog-errors'.format(self.stage_prefix()))
        else:
            self.progress_table = DynamoDBHandler('{}d43-catalog-in-progress'.format(self.stage_prefix())) # pragma: no cover
            self.status_table = DynamoDBHandler('{}d43-catalog-status'.format(self.stage_prefix())) # pragma: no cover
            self.errors_table = DynamoDBHandler('{}d43-catalog-errors'.format(self.stage_prefix())) # pragma: no cover

        self.catalog = {
            "languages": []
        }
        if 's3_handler' in kwargs:
            self.api_handler = kwargs['s3_handler'](self.api_bucket)
        else:
            self.api_handler = S3Handler(self.api_bucket) # pragma: no cover
        if 'ses_handler' in kwargs:
            self.ses_handler = kwargs['ses_handler']()
        else:
            self.ses_handler = SESHandler() # pragma: no cover
        if 'consistency_checker' in kwargs:
            self.checker = kwargs['consistency_checker']()
        else:
            self.checker = ConsistencyChecker() # pragma: no cover
        if 'get_url_handler' in kwargs:
            self.get_url = kwargs['get_url_handler']
        else:
            self.get_url = get_url # pragma: no cover
        if 'url_exists_handler' in kwargs:
            self.url_exists = kwargs['url_exists_handler']
        else:
            self.url_exists = url_exists # pragma: no cover

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

    def _run(self):
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
            status = self._read_status()
            if status and status['state'] == 'complete' and not self._catalog_has_changed(self.catalog):
                response['success'] = True
                response['message'] = 'No changes detected. Catalog not deployed'
            else:
                cat_str = json.dumps(self.catalog, sort_keys=True)
                try:
                    catalog_path = os.path.join(tempfile.gettempdir(), 'catalog.json')
                    write_file(catalog_path, cat_str)
                    c_stats = os.stat(catalog_path)
                    print('New catalog built: {} Kilobytes'.format(c_stats.st_size * 0.001))

                    print('Uploading catalog.json to API')
                    self.api_handler.upload_file(catalog_path, 'v{0}/catalog.json'.format(self.api_version), cache_time=0)
                    self._publish_status()

                    response['success'] = True
                    response['message'] = 'Uploaded new catalog to {0}/v{1}/catalog.json'.format(self.api_url, self.api_version)
                except Exception as e:
                    self.checker.log_error('Unable to save catalog: {0}'.format(e)) # pragma: no cover
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
        results = self.status_table.query_items({'api_version': self.api_version})
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
            {'api_version': self.api_version},
            {
                'state': state,
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'catalog_url': '{0}/v{1}/catalog.json'.format(self.api_url, self.api_version)
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
        for fmt in manifest['formats']:
            errors = checker.check_format(fmt, item)
            if not errors:
                self._strip_build_rules(fmt)
                formats.append(fmt)

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
                    for fmt in project['formats']:
                        self._strip_build_rules(fmt)
                        checker.check_format(fmt, item)
                if not project['categories']:
                    project['categories'] = []
                del project['path']
                resource['projects'].append(project)

            # store formats
            # TRICKY: Bible usfm bundles should always be at the resource level
            is_bible = dc['identifier'] == 'ulb' or dc['identifier'] == 'udb'
            if len(manifest['projects']) == 1 and not (is_bible and self.has_usfm_bundle(formats)):
                # single-project RCs store formats in projects
                if 'formats' in resource['projects'][0]:
                    formats = formats + resource['projects'][0]['formats']
                resource['projects'][0]['formats'] = formats
            else:
                # multi-project RCs store formats in resource
                resource['formats'] = formats

            if 'comment' not in resource: resource['comment'] = ''

            language['resources'].append(resource)
            return True

        return False

    def _strip_build_rules(self, obj):
        """
        Recursively removes 'build_tools' from an object
        :param obj:
        :return:
        """
        if 'build_rules' in obj:
            del obj['build_rules']
        if 'projects' in obj:
            for project in obj['projects']:
                self._strip_build_rules(project)
        if 'formats' in obj:
            for format in obj['formats']:
                self._strip_build_rules(format)
        if 'chapters' in obj:
            for chapter in obj['chapters']:
                self._strip_build_rules(chapter)


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
            catalog_url = '{0}/v{1}/catalog.json'.format(self.api_url, self.api_version)
            current_catalog = json.loads(self.get_url(catalog_url, True))
            same = current_catalog == catalog
            return not same
        except Exception as e:
            return True

    def _handle_errors(self, checker):
        """
        Handles errors and warnings produced by the checker
        :param checker:
        :return:
        """
        if len(checker.all_errors) > 0:
            self.report_error(checker.all_errors, to_email=self.to_email, from_email=self.from_email)
