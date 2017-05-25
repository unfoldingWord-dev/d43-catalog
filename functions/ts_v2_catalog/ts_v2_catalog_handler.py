# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the tS v2 api.
#

import json
import os
from datetime import datetime
import tempfile
from aws_tools.s3_handler import S3Handler
from general_tools.file_utils import write_file
import dateutil.parser

class TsV2CatalogHandler:

    def __init__(self, event, s3_handler):
        """
        Initializes the converter with the catalog from which to generate the v2 catalog
        :param catalog: the latest catalog
        :param  s3_handler: This is passed in so it can be mocked for unit testing
        """
        self.latest_catalog = self.retrieve(event, 'catalog', 'payload')
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')
        if not s3_handler:
            self.s3_handler = S3Handler(self.cdn_bucket)
        else:
            self.s3_handler = s3_handler
        self.temp_dir = tempfile.mkdtemp('', 'tsv2', None)

    def convert_catalog(self):
        """
        Generates the v2 catalog
        :return: the v2 form of the catalog
        """
        cat_languages = []
        uploads = []
        v2_catalog = []

        # walk catalog
        for language in self.latest_catalog['languages']:
            for resource in language['resources']:
                modified = None
                rc_type = None
                if 'formats' in resource:
                    for format in resource['formats']:
                        modified = self._convert_date(format['modified'])
                        if 'type=bundle' in format['format']:
                            rc_type = 'bundle'
                            # TODO: retrieve book data from resource zip
                            break

                for project in resource['projects']:
                    if 'formats' in project:
                        for format in project['formats']:
                            modified = self._convert_date(format['modified'])
                            if 'type=book' in format['format']:
                                rc_type = 'book'
                                # TODO: retrieve book data
                                break

                    if modified is None:
                        raise Exception('Could not find date_modified for {}_{}_{}'.format(language['identifier'], resource['identifier'], project['identifier']))

                    if rc_type == 'book' or rc_type == 'bundle':
                        if project['identifier'] == 'obs': project['sort'] = 1
                        v2_catalog.append({
                            'date_modified': modified,
                            'lang_catalog': '{}/{}/languages.json?date_modified={}'.format(self.cdn_url, project['identifier'], modified),
                            'meta': project['categories'],
                            'slug': project['identifier'],
                            'sort': '{}'.format(project['sort']).zfill(2)
                        })
                        cat_languages.append({
                            'language': {
                                'date_modified': modified,
                                'direction': language['direction'],
                                'name': language['title'],
                                'slug': language['identifier']
                            },
                            'project': {
                                'desc': resource['description'],
                                'meta': project['categories'],
                                'name': project['title'],
                                'slug': project['identifier']
                            },
                            'res_catalog': '{}/{}/{}/resources.json?date_modified={}'.format(self.cdn_url, project['identifier'], language['identifier'], modified)
                        })

        # generate languages catalogs
        for lang in cat_languages:
            project_id = lang['project']['slug']
            del lang['project']['slug']

            temp_lang_file = os.path.join(self.temp_dir, '{}/languages.json'.format(project_id))
            write_file(temp_lang_file, json.dumps(lang, sort_keys=True))
            uploads.append({
                'key': '{}/languages.json'.format(project_id),
                'path': temp_lang_file
            })

        # generate root catalog
        temp_cat_file = os.path.join(self.temp_dir, 'catalog.json')
        write_file(temp_cat_file, json.dumps(v2_catalog, sort_keys=True))
        uploads.append({
            'key': 'catalog.json',
            'path': temp_cat_file
        })

        # upload files
        for upload in uploads:
            self.s3_handler.upload_file(upload['path'], upload['key'])
        return v2_catalog

    def _convert_date(self, date_str):
        """
        Converts a date from the UTC format (used in api v3) to the form in api v2.
        :param date_str: 
        :return: 
        """
        date_obj = dateutil.parser.parse(date_str)
        return date_obj.strftime('%Y%m%d')

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
