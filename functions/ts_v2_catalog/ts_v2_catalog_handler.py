# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the tS v2 api.
#

import json
import yaml
import os
import datetime
import codecs
import re
import tempfile
import time
import zipfile
import markdown
from d43_aws_tools import S3Handler, DynamoDBHandler
from usfm_tools.transform import UsfmTransform
from tools.file_utils import write_file, read_file, unzip
from tools.url_utils import download_file, get_url
import dateutil.parser

class TsV2CatalogHandler:

    def __init__(self, event, s3_handler=None, dynamodb_handler=None, url_handler=None, download_handler=None):
        """
        Initializes the converter with the catalog from which to generate the v2 catalog
        :param  s3_handler: This is passed in so it can be mocked for unit testing
        :param dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param url_handler: This is passed in so it can be mocked for unit testing
        :param download_handler: This is passed in so it can be mocked for unit testing
        """
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.catalog_url = self.retrieve(env_vars, 'catalog_url', 'Environment Vars')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')
        if not s3_handler:
            self.cdn_handler = S3Handler(self.cdn_bucket)
        else:
            self.cdn_handler = s3_handler
        self.temp_dir = tempfile.mkdtemp('', 'tsv2', None)
        if not url_handler:
            self.get_url = get_url
        else:
            self.get_url = url_handler
        if not download_handler:
            self.download_file = download_file
        else:
            self.download_file = download_handler

    def convert_catalog(self):
        """
        Generates the v2 catalog
        :return:
        """
        cat_dict = {}
        supplemental_resources = []
        usx_sources = {}
        obs_sources = {}
        note_sources = {}
        question_sources = {}
        tw_sources = {}

        # retrieve the latest catalog
        catalog_content = self.get_url(self.catalog_url, True)
        if not catalog_content:
            print("ERROR: {0} does not exist".format(self.catalog_url))
            return False
        try:
            self.latest_catalog = json.loads(catalog_content)
        except Exception as e:
            print("ERROR: Failed to load the catalog json: {0}".format(e))
            return False

        # walk catalog
        for language in self.latest_catalog['languages']:
            lid = language['identifier']
            for resource in language['resources']:
                rid = resource['identifier']

                rc_format = None

                if 'formats' in resource:
                    for format in resource['formats']:
                        if not rc_format and self._get_rc_type(format):
                            # locate rc_format (for multi-project RCs)
                            rc_format = format
                        usx_sources.update(self._index_usx_files(lid, rid, format))
                        # TRICKY: bible notes are in the resource
                        note_sources.update(self._index_note_files(lid, rid, format))
                        question_sources.update(self._index_question_files(lid, rid, format))

                for project in resource['projects']:
                    if 'formats' in project:
                        for format in project['formats']:
                            if not rc_format and self._get_rc_type(format):
                                # locate rc_format (for single-project RCs)
                                rc_format = format
                            obs_sources.update(self._index_obs_files(lid, rid, format))
                            if lid not in tw_sources:
                                tw_sources.update(self._index_words_files(lid, rid, format))
                            # TRICKY: obs notes are in the project
                            note_sources.update(self._index_note_files(lid, rid, format))

                    if not rc_format:
                        raise Exception('Could not find a format for {}_{}_{}'.format(language['identifier'], resource['identifier'], project['identifier']))

                    modified = self._convert_date(rc_format['modified'])
                    rc_type = self._get_rc_type(rc_format)

                    if modified is None:
                        modified = time.strftime('%Y%m%d')
                        print('#WARNING: Could not find date_modified for {}_{}_{}'.format(language['identifier'], resource['identifier'], project['identifier']))
                        # raise Exception('Could not find date_modified for {}_{}_{}'.format(language['identifier'], resource['identifier'], project['identifier']))

                    if rc_type == 'book' or rc_type == 'bundle':
                        self._build_catalog_node(cat_dict, language, resource, project, modified)
                    else:
                        # store supplementary resources for processing after catalog nodes have been fully built
                        supplemental_resources.append({
                            'language': language,
                            'resource': resource,
                            'project': project,
                            'modified': modified,
                            'rc_type': rc_type
                        })

        # inject supplementary resources
        for s in supplemental_resources:
            self._add_supplement(cat_dict, s['language'], s['resource'], s['project'], s['modified'], s['rc_type'])

        api_uploads = []

        # upload tw
        for key in tw_sources:
            api_uploads.append(self._prep_data_upload('bible/{}/words.json'.format(key), tw_sources[key]))

        # normalize catalog nodes
        root_cat = []
        for pid in cat_dict:
            project = cat_dict[pid]
            lang_cat = []
            for lid in project['_langs']:
                language = project['_langs'][lid]
                res_cat = []
                for rid in language['_res']:
                    resource = language['_res'][rid]
                    source_key = '$'.join([pid, lid, rid])

                    # TODO: convert and cache notes, questions, tw.
                    if pid == 'obs':
                        note_key = '$'.join([pid, lid, 'obs-tn'])
                    else:
                        note_key = '$'.join([pid, lid, 'tn'])
                    if note_key not in note_sources:
                        resource['notes'] = ''
                    else:
                        api_uploads.append({
                            'key': '{}/{}/{}/notes.json'.format(pid, lid, rid),
                            'path': note_sources[note_key]
                        })
                        del note_sources[note_key]

                    if lid not in tw_sources:
                        resource['terms'] = ''

                    # convert obs source files
                    if rid == 'obs' and source_key in obs_sources:
                        api_uploads.append(
                            self._prep_data_upload('{}/{}/{}/source.json'.format(pid, lid, rid), obs_sources[source_key]))
                        del obs_sources[source_key]

                    # convert usx source files
                    if source_key in usx_sources:
                        source_path = usx_sources[source_key]
                        source = self._generate_source_from_usx(source_path, resource['date_modified'])
                        # TODO: include app_words and language info
                        api_uploads.append(self._prep_data_upload('{}/{}/{}/source.json'.format(pid, lid, rid), source['source']))
                        # TODO: we should probably pull the chunks from the v3 api
                        api_uploads.append(self._prep_data_upload('{}/{}/{}/chunks.json'.format(pid, lid, rid), source['chunks']))
                        del usx_sources[source_key]
                    res_cat.append(resource)
                api_uploads.append(self._prep_data_upload('{}/{}/resources.json'.format(pid, lid), res_cat))

                del language['_res']
                lang_cat.append(language)
            api_uploads.append(self._prep_data_upload('{}/languages.json'.format(pid), lang_cat))

            del  project['_langs']
            root_cat.append(project)
        api_uploads.append(self._prep_data_upload('catalog.json', root_cat))

        # upload files
        for upload in api_uploads:
            self.cdn_handler.upload_file(upload['path'], 'v2/ts/{}'.format(upload['key']))

    def _index_note_files(self, lid, rid, format):

        note_sources = {}

        format_str = format['format']
        if (rid == 'obs-tn' or rid == 'tn') and 'type=help' in format_str:
            zip_file = os.path.join(self.temp_dir, format['url'].split('/')[-1])
            zip_dir = os.path.join(self.temp_dir, lid, rid, 'zip_dir')
            self.download_file(format['url'], zip_file)

            if not os.path.exists(zip_file):
                print('ERROR: could not download file {}'.format(format['url']))
                return {}

            unzip(zip_file, zip_dir)
            help_dir = os.path.join(zip_dir, os.listdir(zip_dir)[0])

            try:
                manifest = yaml.load(read_file(os.path.join(help_dir, 'manifest.yaml')))
            except Exception as e:
                print('ERROR: could not read manifest in {}'.format(format['url']))
                return {}

            # ensure the manifest matches
            dc = manifest['dublin_core']
            if dc['identifier'] != rid or dc['language']['identifier'] != lid:
                return {}

            for project in manifest['projects']:
                pid = project['identifier']
                key = '$'.join([pid, lid, rid])
                note_dir = os.path.normpath(os.path.join(help_dir, project['path']))
                note_json_file = os.path.normpath(os.path.join(help_dir, project['path'] + '_notes.json'))
                # TODO: process note_dir and generate json file to upload
                write_file(note_json_file, json.dumps({}, sort_keys=True))
                note_sources[key] = note_json_file

        return note_sources

    def _index_question_files(self, lid, rid, format):
        # TODO: finish this
        return {}


    def _index_words_files(self, lid, rid, format):
        """
        Returns an array of markdown files found in a tW dictionary
        :param lid:
        :param rid:
        :param format:
        :return:
        """
        word_title_re = re.compile('^#([^#]*)#?', re.UNICODE)
        h2_re = re.compile('^##([^#]*)#*', re.UNICODE)
        obs_example_re = re.compile('\_*\[([^\[\]]+)\]\(([^\(\)]+)\)_*(.*)', re.UNICODE | re.IGNORECASE)
        block_re = re.compile('^##', re.MULTILINE | re.UNICODE)

        words = []
        format_str = format['format']
        if rid == 'tw' and 'type=dict' in format_str:
            zip_file = os.path.join(self.temp_dir, format['url'].split('/')[-1])
            zip_dir = os.path.join(self.temp_dir, lid, rid, 'zip_dir')
            self.download_file(format['url'], zip_file)

            if not os.path.exists(zip_file):
                print('ERROR: could not download file {}'.format(format['url']))
                return {}

            unzip(zip_file, zip_dir)
            dict_dir = os.path.join(zip_dir, os.listdir(zip_dir)[0])

            try:
                manifest = yaml.load(read_file(os.path.join(dict_dir, 'manifest.yaml')))
            except Exception as e:
                print('ERROR: could not read manifest in {}'.format(format['url']))
                return {}

            # ensure the manifest matches
            dc = manifest['dublin_core']
            if dc['identifier'] != rid or dc['language']['identifier'] != lid:
                return {}

            # TRICKY: there should only be one project
            for project in manifest['projects']:
                pid = project['identifier']
                content_dir = os.path.join(dict_dir, project['path'])
                categories = os.listdir(content_dir)
                for cat in categories:
                    cat_dir = os.path.join(content_dir, cat)
                    word_files = os.listdir(cat_dir)
                    for word in word_files:
                        word_path = os.path.join(cat_dir, word)
                        word_id = word.split('.md')[0]
                        word_content = read_file(word_path)

                        # TRICKY: the title is always at the top
                        title_match = word_title_re.match(word_content)
                        if title_match:
                            title = title_match.group(1)
                        else:
                            print('ERROR: missing title in {}'.format(word_path))
                            continue
                        word_content = word_title_re.sub('', word_content).strip()

                        # TRICKY: the definition title is always after the title
                        def_title = ''
                        def_title_match = h2_re.match(word_content)
                        if def_title_match:
                            def_title = def_title_match.group(1).strip()
                            word_content = h2_re.sub('', word_content).strip()
                        else:
                            print('ERROR: missing definition title in {}'.format(word_path))

                        # find obs examples
                        blocks = block_re.split(word_content)
                        cleaned_blocks = []
                        examples = []
                        for block in blocks:
                            if 'examples from the bible stories' in block.lower():
                                for link in obs_example_re.findall(block):
                                    if 'obs' not in link[1]:
                                        print('ERROR: non-obs link found in passage examples: {}'.format(link[1]))
                                    else:
                                        examples.append({
                                            'ref': link[0].replace(':', '-'),
                                            'text': markdown.markdown(link[2].strip()) # TODO: we may need to preserve links in markdown format
                                        })
                            else:
                                cleaned_blocks.append(block)
                        word_content = '##'.join(cleaned_blocks)

                        words.append({
                            'aliases': [a.strip() for a in title.split(',') if a.strip() != word_id and a.strip() != title.strip()],
                            'cf': [], # TODO: add see also ids. search for tw links
                            'def': markdown.markdown(word_content), # TODO: we may need to preserve links in markdown format
                            'def_title': def_title,
                            'ex': examples,
                            'id': word_id,
                            'sub': '',
                            'term': title.strip()
                        })

            words.append({
                'date_modified': dc['modified'].replace('-', '')
            })
            return {
                lid: words
            }
        return {}

    def _index_obs_files(self, lid, rid, format):
        """
        Returns an array of markdown files found in a OBS book.
        This should contain a single file per chapter
        :param lid:
        :param rid:
        :param format:
        :return:
        """
        obs_sources = {}
        format_str = format['format']
        if rid == 'obs' and 'type=book' in format_str:
            zip_file = os.path.join(self.temp_dir, format['url'].split('/')[-1])
            zip_dir = os.path.join(self.temp_dir, lid, rid, 'zip_dir')
            self.download_file(format['url'], zip_file)

            if not os.path.exists(zip_file):
                print('ERROR: could not download file {}'.format(format['url']))
                return obs_sources

            unzip(zip_file, zip_dir)
            book_dir = os.path.join(zip_dir, os.listdir(zip_dir)[0])

            try:
                manifest = yaml.load(read_file(os.path.join(book_dir, 'manifest.yaml')))
            except Exception as e:
                print('ERROR: could not read manifest in {}'.format(format['url']))
                return obs_sources

            # ensure the manifest matches
            dc = manifest['dublin_core']
            if dc['identifier'] != rid or dc['language']['identifier'] != lid:
                return obs_sources

            for project in manifest['projects']:
                pid = project['identifier']
                content_dir = os.path.join(book_dir, project['path'])
                key = '$'.join([pid, lid, rid])
                chapters_json = self._obs_chapters_to_json(os.path.normpath(content_dir))

                # app words
                app_words = {}
                app_words_file = os.path.join(book_dir, '.apps', 'uw', 'app_words.json')
                if os.path.exists(app_words_file):
                    try:
                        app_words = json.loads(read_file(app_words_file))
                    except Exception as e:
                        print('ERROR: failed to load app words: {}'.format(e))

                obs_sources[key] = {
                    'app_words': app_words,
                    'chapters': chapters_json,
                    'date_modified': dc['modified'].replace('-', ''),
                    'direction': dc['language']['direction'],
                    'language': dc['language']['identifier']
                }

        return obs_sources

    def _obs_chapters_to_json(self, dir):
        """

        :param dir: the obs book content directory
        :param date_modified:
        :return:
        """
        obs_title_re = re.compile('^\s*#+\s*(.*)', re.UNICODE)
        obs_footer_re = re.compile('\_+([^\_]*)\_+$', re.UNICODE)
        obs_image_re = re.compile('.*!\[OBS Image\]\(.*\).*', re.IGNORECASE | re.UNICODE)
        chapters = []
        for chapter_file in os.listdir(dir):
            chapter_slug = chapter_file.split('.md')[0]
            path = os.path.join(dir, chapter_file)
            if os.path.isfile(path):
                chapter_file = os.path.join(dir, path)
                chapter_str = read_file(chapter_file).strip()

                title_match = obs_title_re.match(chapter_str)
                if title_match:
                    title = title_match.group(1)
                else:
                    print('ERROR: missing title in {}'.format(chapter_file))
                    continue
                chapter_str = obs_title_re.sub('', chapter_str).strip()
                lines = chapter_str.split('\n')
                reference_match = obs_footer_re.match(lines[-1])
                if reference_match:
                    reference = reference_match.group(1)
                else:
                    print('ERROR: missing reference in {}'.format(chapter_file))
                    continue
                chapter_str = '\n'.join(lines[0:-1]).strip()
                chunks = obs_image_re.split(chapter_str)

                frames = []
                chunk_index = 0
                for chunk in chunks:
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    chunk_index += 1
                    id = '{}-{}'.format(chapter_slug, '{}'.format(chunk_index).zfill(2))
                    frames.append({
                        'id': id,
                        'img': 'https://cdn.door43.org/obs/jpg/360px/obs-en-{}.jpg'.format(id),
                        'text': chunk
                    })
                chapters.append({
                    'frames': frames,
                    'number': chapter_slug,
                    'ref': reference,
                    'title': title
                })

        return chapters

    def _index_usx_files(self, lid, rid, format):
        """
        Converts a USFM bundle into USX files and returns an array of usx file paths
        :param lid:
        :param rid:
        :param format:
        :return:
        """
        usx_sources = {}

        format_str = format['format']
        if 'application/zip' in format_str and 'usfm' in format_str:
            zip_file = os.path.join(self.temp_dir, format['url'].split('/')[-1])
            zip_dir = os.path.join(self.temp_dir, lid, rid, 'zip_dir')
            self.download_file(format['url'], zip_file)

            if not os.path.exists(zip_file):
                print('ERROR: could not download file {}'.format(format['url']))
                return usx_sources

            unzip(zip_file, zip_dir)
            usfm_bundle_dir = os.path.join(zip_dir, os.listdir(zip_dir)[0])

            try:
                manifest = yaml.load(read_file(os.path.join(usfm_bundle_dir, 'manifest.yaml')))
            except Exception as e:
                print('ERROR: could not read manifest in {}'.format(format['url']))
                return usx_sources

            # ensure the manifest matches
            dc = manifest['dublin_core']
            if dc['identifier'] != rid or dc['language']['identifier'] != lid:
                return usx_sources

            usx_path = os.path.join(usfm_bundle_dir, 'usx')
            UsfmTransform.buildUSX(usfm_bundle_dir, usx_path, '', True)
            for project in manifest['projects']:
                pid = project['identifier']
                key = '$'.join([pid, lid, rid])
                usx_sources[key] = os.path.normpath(os.path.join(usx_path, '{}.usx'.format(pid.upper())))

        return usx_sources

    def _prep_data_upload(self, key, data):
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
        try:
            return date_obj.strftime('%Y%m%d')
        except:
            return None

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

    def _usx_to_json(self, usx):
        """
        Iterates through the source and splits it into frames based on the
        s5 markers.
        :param usx:
        """
        verse_re = re.compile(r'<verse number="([0-9]*)', re.UNICODE)
        chunk_marker = '<note caller="u" style="s5"></note>'
        chapters = []
        chp = ''
        fr_id = 0
        chp_num = 0
        fr_list = []
        current_vs = -1
        for line in usx:
            if line.startswith('\n'):
                continue

            if "verse number" in line:
                current_vs = verse_re.search(line).group(1)

            if 'chapter number' in line:
                if chp:
                    if fr_list:
                        fr_text = '\n'.join(fr_list)
                        try:
                            first_vs = verse_re.search(fr_text).group(1)
                        except AttributeError:
                            print('myError, chp {0}'.format(chp_num))
                            print('Text: {0}'.format(fr_text))
                            continue
                        chp['frames'].append({'id': '{0}-{1}'.format(
                            str(chp_num).zfill(2), first_vs.zfill(2)),
                            'img': '',
                            'format': 'usx',
                            'text': fr_text,
                            'lastvs': current_vs
                        })
                    chapters.append(chp)
                chp_num += 1
                chp = {'number': str(chp_num).zfill(2),
                       'ref': '',
                       'title': '',
                       'frames': []
                       }
                fr_list = []
                continue

            if chunk_marker in line:
                if chp_num == 0:
                    continue

                # is there something else on the line with it? (probably an end-of-paragraph marker)
                if len(line.strip()) > len(chunk_marker):
                    # get the text following the chunk marker
                    rest_of_line = line.replace(chunk_marker, '')

                    # append the text to the previous line, removing the unnecessary \n
                    fr_list[-1] = fr_list[-1][:-1] + rest_of_line

                if fr_list:
                    fr_text = '\n'.join(fr_list)
                    try:
                        first_vs = verse_re.search(fr_text).group(1)
                    except AttributeError as e:
                        print('Error, chp {0}'.format(chp_num))
                        print('Text: {0}'.format(fr_text))
                        raise e

                    chp['frames'].append({'id': '{0}-{1}'.format(
                        str(chp_num).zfill(2), first_vs.zfill(2)),
                        'img': '',
                        'format': 'usx',
                        'text': fr_text,
                        'lastvs': current_vs
                    })
                    fr_list = []

                continue

            fr_list.append(line)

        # Append the last frame and the last chapter
        chp['frames'].append({
            'id': '{0}-{1}'.format(str(chp_num).zfill(2), str(fr_id).zfill(2)),
            'img': '',
            'format': 'usx',
            'text': '\n'.join(fr_list),
            'lastvs': current_vs
        })
        chapters.append(chp)
        return chapters

    def _read_chunks(self, book):
        chunks = []
        verse_re = re.compile(r'<verse number="([0-9]*)', re.UNICODE)
        for c in book:
            for frame in c['frames']:
                chunks.append({'id': frame['id'],
                               'firstvs': verse_re.search(frame['text']).group(1),
                               'lastvs': frame["lastvs"]
                               })
        return chunks

    def _generate_source_from_usx(self, path, date_modified):
        # use utf-8-sig to remove the byte order mark
        with codecs.open(path, 'r', encoding='utf-8-sig') as in_file:
            usx = in_file.readlines()

        book = self._usx_to_json(usx)
        chunks = self._read_chunks(book)

        return {
            'source': {
                'chapters': book,
                'date_modified': date_modified
            },
            'chunks': chunks
        }
