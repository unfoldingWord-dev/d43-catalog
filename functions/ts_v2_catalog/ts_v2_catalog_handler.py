# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the tS v2 api.
#

import json
import os
from datetime import datetime
import re
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
        cat_dict = {}
        supplementary_resources = []
        # walk catalog
        for language in self.latest_catalog['languages']:
            for resource in language['resources']:
                rc_format = None
                # locate rc_format (for multi-project RCs)
                if 'formats' in resource:
                    for format in resource['formats']:
                        if self._get_rc_type(format):
                            rc_format = format
                            break

                for project in resource['projects']:
                    # locate rc_format (for single-project RCs)
                    if 'formats' in project:
                        for format in project['formats']:
                            if self._get_rc_type(format):
                                rc_format = format
                                break

                    modified = self._convert_date(rc_format['modified'])
                    rc_type = self._get_rc_type(rc_format)
                    if modified is None:
                        raise Exception('Could not find date_modified for {}_{}_{}'.format(language['identifier'], resource['identifier'], project['identifier']))

                    if rc_type == 'book' or rc_type == 'bundle':
                        self._build_catalog_node(cat_dict, language, resource, project, modified)
                    else:
                        # store supplementary resources for processing after catalog nodes have been fully built
                        supplementary_resources.append({
                            'language': language,
                            'resource': resource,
                            'project': project,
                            'modified': modified,
                            'rc_type': rc_type
                        })

        # inject supplementary resources
        for s in supplementary_resources:
            self._add_supplement(cat_dict, s['language'], s['resource'], s['project'], s['modified'], s['rc_type'])

        # normalize catalog nodes
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

    def _get_rc_type(self, format):
        """
        Returns the first resource type found in an array of formats
        :param ary: 
        :return: 
        """
        re_type = re.compile(r'type=(\w+)', re.UNICODE|re.IGNORECASE)
        if 'conformsto=rc0.2' in format['format'] and 'type' in format['format']:
            match = re_type.search(format['format'])
            return match.group(1)
        return None

    def _add_supplement(self, catalog, language, resource, project, modified, rc_type):
        """
        Adds supplementary helps to the catalog nodes
        :param catalog: 
        :param language: 
        :param resource: 
        :param project: 
        :param modified: 
        :param rc_type: 
        :return: 
        """
        lid = language['identifier']

        if rc_type == 'help':
            pid = project['identifier']
            for rid in catalog[pid]['_langs'][lid]['_res']:
                res = catalog[pid]['_langs'][lid]['_res'][rid]
                if 'tn' in resource['identifier']:
                    if pid == 'obs':
                        res.update({
                            'notes': 'https://api.unfoldingword.org/{0}/txt/1/{1}/tN-{1}.json?date_modified={2}'.format(
                                pid, lid, modified)
                        })
                    else:
                        res.update({
                            'notes': 'https://api.unfoldingword.org/ts/txt/2/{}/{}/notes.json?date_modified={}'.format(
                                pid, lid, modified)
                        })
                elif 'tq' in resource['identifier']:
                    if pid == 'obs':
                        res.update({
                            'checking_questions': 'https://api.unfoldingword.org/{0}/txt/1/{1}/CQ-{1}.json?date_modified={2}'.format(pid, lid,  modified)
                        })
                    else:
                        res.update({
                            'checking_questions': 'https://api.unfoldingword.org/ts/txt/2/{}/{}/questions.json?date_modified={}'.format(
                                pid, lid, modified)
                        })
        elif rc_type == 'dict':
            for pid in catalog:
                for rid in catalog[pid]['_langs'][lid]['_res']:
                    res = catalog[pid]['_langs'][lid]['_res'][rid]
                    if pid == 'obs':
                        res.update({
                            'terms': 'https://api.unfoldingword.org/obs/txt/1/{0}/kt-{0}.json?date_modified={1}'.format(lid, modified)
                        })
                    else:
                        res.update({
                            'terms': 'https://api.unfoldingword.org/ts/txt/2/bible/{}/terms.json?date_modified={}'.format(lid, modified)
                        })

    def _build_catalog_node(self, catalog, language, resource, project, modified):
        """
        Creates/updates a node in the catalog
        :param catalog: 
        :param language: 
        :param resource: 
        :param project: 
        :param modified: 
        :return: 
        """
        lid = language['identifier']
        rid = resource['identifier']
        pid = project['identifier']

        # TRICKY: v2 api sorted obs with 1
        if pid == 'obs': project['sort'] = 1

        # init catalog nodes
        if pid not in catalog: catalog[pid] = {'_langs': {}}
        if lid not in catalog[pid]['_langs']: catalog[pid]['_langs'][lid] = {'_res': {}, 'language': {}}
        if rid not in catalog[pid]['_langs'][lid]['_res']: catalog[pid]['_langs'][lid]['_res'][rid] = {}

        # TRICKY: we must process the modified date in the order of resource, language, project to propagate dates correctly

        # resource
        res = catalog[pid]['_langs'][lid]['_res'][rid]
        r_modified = self._max_modified(res, modified) # TRICKY: dates bubble up from project
        comments = ''  # TRICKY: comments are not officially supported in RCs but we use them if available
        if 'comment' in resource: comments = resource['comment']
        if pid == 'obs':
            source_url = 'https://api.unfoldingword.org/obs/txt/1/{0}/obs-{0}.json?date_modified={1}'.format(lid, r_modified)
        else:
            source_url = 'https://api.unfoldingword.org/ts/txt/2/{0}/{1}/ulb/source.json?date_modified={2}'.format(pid, lid, r_modified)
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
                'source_text': resource['source'][0]['language'],  # v2 can only handle one source
                'source_text_version': resource['source'][0]['version'],  # v2 can only handle one source
                'version': resource['version']
            },
            'checking_questions': '',
            'source': source_url,
            'terms': '',
            'tw_cat': ''
        })
        # english projects have tw_cat
        if lid == 'en':
            if pid == 'obs':
                res.update({
                    'tw_cat': 'https://api.unfoldingword.org/obs/txt/1/{0}/tw_cat-{0}.json?date_modified={1}'.format(lid, r_modified)
                })
            else:
                res.update({
                    'tw_cat': 'https://api.unfoldingword.org/ts/txt/2/{}/{}/tw_cat.json?date_modified={}'.format(pid, lid, r_modified)
                })

        # bible projects have usfm
        if pid != 'obs':
            res.update({
                'usfm': 'https://api.unfoldingword.org/{0}/txt/1/{0}-{1}/{2}-{3}.usfm?date_modified={4}'.format(rid, lid, '{}'.format(project['sort']).zfill(2), pid.upper(), r_modified)
            })

        # language
        lang = catalog[pid]['_langs'][lid]
        l_modified = self._max_modified(lang['language'], r_modified) # TRICKY: dates bubble up from resource
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

        # project
        p_modified = self._max_modified(catalog[pid], l_modified)
        catalog[pid].update({
            'date_modified': p_modified,
            'lang_catalog': '{}/{}/languages.json?date_modified={}'.format(self.cdn_url, pid, p_modified),
            'meta': project['categories'],
            'slug': pid,
            'sort': '{}'.format(project['sort']).zfill(2)
        })

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
