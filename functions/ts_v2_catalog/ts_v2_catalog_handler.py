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
        :return:
        """
        cat_languages = {} # grouped by projects
        cat_resources = {} # grouped by project and language
        uploads = []
        v2_catalog = []

        cat_dict = {}
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

                        self._build_catalog_branch(cat_dict, language, resource, project, modified)

        # normalize catalog branches
        uploads = []
        root_cat = []
        for pid in cat_dict:
            project = cat_dict[pid]
            lang_cat = []
            for lid in project['_langs']:
                language = project['_langs'][lid]
                res_cat = []
                for rid in language['_res']:
                    resource = language['_res'][rid]
                    res_cat.append(resource)
                uploads.append(self._prep_upload('{}/{}/resources.json'.format(pid, lid), res_cat))

                del language['_res']
                lang_cat.append(language)
            uploads.append(self._prep_upload('{}/languages.json'.format(pid), lang_cat))

            del  project['_langs']
            root_cat.append(project)
        uploads.append(self._prep_upload('catalog.json', root_cat))

        # upload files
        for upload in uploads:
            self.s3_handler.upload_file(upload['path'], upload['key'])

    def _prep_upload(self, key, data):
        """
        Prepares some data for upload to s3
        :param key: 
        :param data: 
        :return: 
        """
        temp_file = os.path.join(self.temp_dir, key)
        write_file(temp_file, json.dumps(data, sort_keys=True))
        return {
            'key': key,
            'path': temp_file
        }

    def _build_catalog_branch(self, catalog, language, resource, project, modified):
        lid = language['identifier']
        rid = resource['identifier']
        pid = project['identifier']

        # init catalog nodes
        if pid not in catalog: catalog[pid] = {'_langs': {}}
        if lid not in catalog[pid]['_langs']: catalog[pid]['_langs'][lid] = {'_res': {}}
        if rid not in catalog[pid]['_langs'][lid]['_res']: catalog[pid]['_langs'][lid]['_res'][rid] = {}

        ## build nodes

        # project
        p_modified = self._max_modified(catalog[pid], modified)
        catalog[pid].update({
            'date_modified': p_modified,
            'lang_catalog': '{}/{}/languages.json?date_modified={}'.format(self.cdn_url, pid, p_modified),
            'meta': project['categories'],
            'slug': pid,
            'sort': '{}'.format(project['sort']).zfill(2)
        })

        # resource
        res = catalog[pid]['_langs'][lid]['_res'][rid]
        r_modified = self._max_modified(res, p_modified) # TRICKY: dates bubble up from project
        comments = ''  # TRICKY: comments are not officially supported in RCs but we use them if available
        if 'comment' in resource: comments = resource['comment']
        res.update({
            'date_modified': r_modified,
            'name': resource['title'],
            'notes': '',
            'slug': resource['identifier'],
            'status': {
                'checking_entity': ', '.join(resource['checking']['checking_entity']),
                'checking_level': resource['checking']['checking_level'],
                'comments': comments,
                'contributors': '; '.join(resource['contributor']),
                'publish_date': resource['issued'],
                'source_text': resource['source'][0]['identifier'],  # v2 can only handle one source
                'source_text_version': resource['source'][0]['version'],  # v2 can only handle one source
                'version': resource['version']
            },
            # TODO: include links as needed
            'checking_questions': '',
            'source': '',
            'terms': '',
            'tw_cat': ''
        })

        # language
        lang = catalog[pid]['_langs'][lid]
        l_modified = self._max_modified(lang, r_modified) # TRICKY: dates bubble up from resource
        description = ''
        if rid == 'obs': description = resource['description']
        cat_lang = {
            'language': {
                'date_modified': l_modified,
                'direction': language['direction'],
                'name': language['title'],
                'slug': lid
            },
            'project': {
                'desc': description,
                'meta': project['categories'],
                'name': project['title']
            },
            'res_catalog': '{}/{}/{}/resources.json?date_modified={}'.format(self.cdn_url, pid, lid, l_modified)
        }
        if 'ulb' == rid or 'udb' == rid:
            cat_lang['project']['sort'] = '{}'.format(project['sort'])
        lang.update(cat_lang)

    def _max_modified(self, obj, modified):
        """
        Return the largest modified date
        If the object does not have a date_modified the argument is returned
        :param obj: 
        :param modified: 
        :return: 
        """
        if 'date_modified' not in obj or int(obj['date_modified']) < int(modified):
            return modified
        else:
            return obj['date_modified']

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
