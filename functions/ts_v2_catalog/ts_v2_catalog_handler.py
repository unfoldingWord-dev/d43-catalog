# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the tS v2 api.
#
import hashlib
import json
import yaml
import os
import codecs
import re
import tempfile
import time
import markdown
from d43_aws_tools import S3Handler
from usfm_tools.transform import UsfmTransform
from tools.file_utils import write_file, read_file, unzip
from tools.url_utils import download_file, get_url
import dateutil.parser

class TsV2CatalogHandler:

    cdn_rooth_path = 'v2/ts'

    def __init__(self, event, s3_handler=None, url_handler=None, download_handler=None):
        """
        Initializes the converter with the catalog from which to generate the v2 catalog
        :param  s3_handler: This is passed in so it can be mocked for unit testing
        :param url_handler: This is passed in so it can be mocked for unit testing
        :param download_handler: This is passed in so it can be mocked for unit testing
        """
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.catalog_url = self.retrieve(env_vars, 'catalog_url', 'Environment Vars')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars')
        self.cdn_url = self.cdn_url.rstrip('/')
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
                        # TRICKY: bible notes and questions are in the resource
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
                            # TRICKY: obs notes and questions are in the project
                            note_sources.update(self._index_note_files(lid, rid, format))
                            question_sources.update(self._index_question_files(lid, rid, format))

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
                    # upload tQ
                    if pid == 'obs':
                        question_key = '$'.join([pid, lid, 'obs-tq'])
                    else:
                        question_key = '$'.join([pid, lid, 'tq'])
                    if question_key not in question_sources:
                        resource['checking_questions'] = ''
                    else:
                        api_uploads.append({
                            # TRICKY: questions are organized by project not resource
                            'key': '{}/{}/questions.json'.format(pid, lid),
                            'path': question_sources[question_key]
                        })
                        # del question_sources[question_key]

                    # upload tN
                    if pid == 'obs':
                        note_key = '$'.join([pid, lid, 'obs-tn'])
                    else:
                        note_key = '$'.join([pid, lid, 'tn'])
                    if note_key not in note_sources:
                        resource['notes'] = ''
                    else:
                        api_uploads.append({
                            # TRICKY: notes are organized by project not resource
                            'key': '{}/{}/notes.json'.format(pid, lid),
                            'path': note_sources[note_key]
                        })
                        # del note_sources[note_key]

                    # exclude tw if not in sources
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
            self.cdn_handler.upload_file(upload['path'], '{}/{}'.format(TsV2CatalogHandler.cdn_rooth_path, upload['key']))

    def _index_note_files(self, lid, rid, format):
        note_general_re = re.compile('^([^#]+)', re.UNICODE)
        note_re = re.compile('^#+([^#\n]+)#*([^#]*)', re.UNICODE | re.MULTILINE | re.DOTALL)
        note_sources = {}

        format_str = format['format']
        if (rid == 'obs-tn' or rid == 'tn') and 'type=help' in format_str:
            rc_dir = self._retrieve_rc(lid, rid, format['url'])
            if not rc_dir: return {}

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            dc = manifest['dublin_core']

            for project in manifest['projects']:
                pid = project['identifier']
                key = '$'.join([pid, lid, rid])
                note_dir = os.path.normpath(os.path.join(rc_dir, project['path']))
                note_json_file = os.path.normpath(os.path.join(rc_dir, project['path'] + '_notes.json'))
                note_json = []

                chapters = os.listdir(note_dir)
                for chapter in chapters:
                    if chapter == 'front': continue
                    chapter_dir = os.path.join(note_dir, chapter)
                    chunks = os.listdir(chapter_dir)
                    for chunk in chunks:
                        if chunk == 'intro.md': continue
                        notes = []
                        chunk_file = os.path.join(chapter_dir, chunk)
                        chunk = chunk.split('.')[0]
                        chunk_body = read_file(chunk_file)
                        chunk_body = self._convert_rc_links(chunk_body)
                        general_notes = note_general_re.search(chunk_body)

                        if general_notes:
                            chunk_body = note_general_re.sub('', chunk_body)
                            notes.append({
                                'ref': 'General Information',
                                'text': general_notes.group(0).strip()
                            })

                        for note in note_re.findall(chunk_body):
                            notes.append({
                                'ref': note[0].strip(),
                                'text': note[1].strip()
                            })

                        note_json.append({
                            'id': '{}-{}'.format(chapter, chunk),
                            'tn': notes
                        })

                note_json.append({'date_modified': dc['modified'].replace('-', '')})
                write_file(note_json_file, json.dumps(note_json, sort_keys=True))
                note_sources[key] = note_json_file

        return note_sources

    def _index_question_files(self, lid, rid, format):
        question_re = re.compile('^#+([^#\n]+)#*([^#]*)', re.UNICODE | re.MULTILINE | re.DOTALL)
        question_sources = {}

        format_str = format['format']
        if (rid == 'obs-tq' or rid == 'tq') and 'type=help' in format_str:
            rc_dir = self._retrieve_rc(lid, rid, format['url'])
            if not rc_dir: return {}

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            dc = manifest['dublin_core']

            for project in manifest['projects']:
                pid = project['identifier']
                key = '$'.join([pid, lid, rid])
                question_dir = os.path.normpath(os.path.join(rc_dir, project['path']))
                question_json_file = os.path.normpath(os.path.join(rc_dir, project['path'] + '_questions.json'))
                question_json = []

                chapters = os.listdir(question_dir)
                for chapter in chapters:
                    unique_questions = {}
                    chapter_dir = os.path.join(question_dir, chapter)
                    chunks = os.listdir(chapter_dir)
                    for chunk in chunks:
                        chunk_file = os.path.join(chapter_dir, chunk)
                        chunk = chunk.split('.')[0]
                        chunk_body = read_file(chunk_file)

                        for question in question_re.findall(chunk_body):
                            hasher = hashlib.md5()
                            hasher.update(question[1].strip())
                            question_hash = hasher.hexdigest()
                            if question_hash not in unique_questions:
                                # insert unique question
                                unique_questions[question_hash] = {
                                    'q': question[0].strip(),
                                    'a': question[1].strip(),
                                    'ref': [
                                        '{}-{}'.format(chapter, chunk)
                                    ]
                                }
                            else:
                                # append new reference
                                unique_questions[question_hash]['ref'].append('{}-{}'.format(chapter, chunk))

                    question_array = []
                    for hash in unique_questions:
                        question_array.append(unique_questions[hash])

                    question_json.append({
                        'id': chapter,
                        'cq': question_array
                    })

                question_json.append({'date_modified': dc['modified'].replace('-', '')})
                write_file(question_json_file, json.dumps(question_json, sort_keys=True))
                question_sources[key] = question_json_file

        return question_sources


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
            rc_dir = self._retrieve_rc(lid, rid, format['url'])
            if not rc_dir: return {}

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            dc = manifest['dublin_core']

            # TRICKY: there should only be one project
            for project in manifest['projects']:
                pid = project['identifier']
                content_dir = os.path.join(rc_dir, project['path'])
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
            rc_dir = self._retrieve_rc(lid, rid, format['url'])
            if not rc_dir: return obs_sources

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            dc = manifest['dublin_core']

            for project in manifest['projects']:
                pid = project['identifier']
                content_dir = os.path.join(rc_dir, project['path'])
                key = '$'.join([pid, lid, rid])
                chapters_json = self._obs_chapters_to_json(os.path.normpath(content_dir))

                # app words
                app_words = {}
                app_words_file = os.path.join(rc_dir, '.apps', 'uw', 'app_words.json')
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
            if chapter_file == 'config.yaml' or chapter_file == 'toc.yaml':
                # TODO: read info from config
                continue
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
            rc_dir = self._retrieve_rc(lid, rid, format['url'])
            if not rc_dir: return usx_sources

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))

            usx_path = os.path.join(rc_dir, 'usx')
            UsfmTransform.buildUSX(rc_dir, usx_path, '', True)
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
                    res.update({
                        'notes': '{}/{}/{}/{}/notes.json?date_modified={}'.format(
                            self.cdn_url,
                            TsV2CatalogHandler.cdn_rooth_path,
                            pid, lid, modified)
                    })
                elif 'tq' in resource['identifier']:
                    res.update({
                        'checking_questions': '{}/{}/{}/{}/questions.json?date_modified={}'.format(
                            self.cdn_url,
                            TsV2CatalogHandler.cdn_rooth_path,
                            pid, lid, modified)
                    })
        elif rc_type == 'dict':
            for pid in catalog:
                for rid in catalog[pid]['_langs'][lid]['_res']:
                    res = catalog[pid]['_langs'][lid]['_res'][rid]
                    # TRICKY: obs and Bible now use the same words
                    res.update({
                        'terms': '{}/{}/bible/{}/words.json?date_modified={}'.format(
                            self.cdn_url,
                            TsV2CatalogHandler.cdn_rooth_path,
                            lid, modified)
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
        # if pid == 'obs':
        #     source_url = 'https://api.unfoldingword.org/v2/ts/{}/{}/source.json?date_modified={}'.format(pid, lid, r_modified)
        # else:
        source_url = '{}/{}/{}/{}/{}/source.json?date_modified={}'.format(
            self.cdn_url,
            TsV2CatalogHandler.cdn_rooth_path,
            pid, lid, rid, r_modified)
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
            res.update({
                'tw_cat': '{}/{}/{}/{}/tw_cat.json?date_modified={}'.format(
                    self.cdn_url,
                    TsV2CatalogHandler.cdn_rooth_path,
                    pid, lid, r_modified)
            })

        # bible projects have usfm
        if pid != 'obs':
            res.update({
                'usfm': '{}/{}/{}/{}/{}-{}.usfm?date_modified={}'.format(
                    self.cdn_url,
                    TsV2CatalogHandler.cdn_rooth_path,
                    rid, lid, '{}'.format(project['sort']).zfill(2), pid.upper(), r_modified)
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
            'res_catalog': '{}/{}/{}/{}/resources.json?date_modified={}'.format(self.cdn_url, TsV2CatalogHandler.cdn_rooth_path, pid, lid, l_modified)
        }
        if 'ulb' == rid or 'udb' == rid:
            cat_lang['project']['sort'] = '{}'.format(project['sort'])
        lang.update(cat_lang)

        # project
        p_modified = self._max_modified(catalog[pid], l_modified)
        catalog[pid].update({
            'date_modified': p_modified,
            'lang_catalog': '{}/{}/{}/languages.json?date_modified={}'.format(self.cdn_url, TsV2CatalogHandler.cdn_rooth_path, pid, p_modified),
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

    def _retrieve_rc(self, lid, rid, url):
        """
        Downloads a resource container from a url, validates it, and prepares it for reading
        :param lid: the language code of the RC
        :param rid: the resource code of the RC
        :param url: the url from which to download the RC
        :return: the path to the readable RC or None if an error occured.
        """
        zip_file = os.path.join(self.temp_dir, url.split('/')[-1])
        zip_dir = os.path.join(self.temp_dir, lid, rid, 'zip_dir')
        self.download_file(url, zip_file)

        if not os.path.exists(zip_file):
            print('ERROR: could not download file {}'.format(url))
            return None

        unzip(zip_file, zip_dir)
        rc_dir = os.path.join(zip_dir, os.listdir(zip_dir)[0])

        try:
            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
        except Exception as e:
            print('ERROR: could not read manifest in {}'.format(url))
            return None

        # ensure the manifest matches
        dc = manifest['dublin_core']
        if dc['identifier'] != rid or dc['language']['identifier'] != lid:
            print('ERROR: the downloaded RC does not match the expected language ({}) and resource ({}). Found {}-{} instead'.format(lid, rid, dc['language']['identifier'], dc['identifier']))
            return None

        return rc_dir

    def _convert_rc_links(self, content):
        """
        Converts rc links in the content to legacy links
        :param content:
        :return:
        """
        rc_titled_link_re = re.compile('\[[^\[\]]+\]\((rc\:\/\/([^\[\]]+))\)')
        rc_link_re = re.compile('\[\[(rc\:\/\/([^\[\]]+))\]\]')

        # find links
        titled_links = rc_titled_link_re.findall(content)
        if not titled_links: titled_links = []
        links = rc_link_re.findall(content)
        if not links: links = []
        links = links + titled_links

        # process links
        for link in links:
            components = link[1].split('/')
            lid = components[0]
            rid = components[1]
            rtype = components[2]
            pid = components[3].replace('-', '_')

            new_link = link[0]
            if rid == 'ta':
                module = components[4].replace('-', '_')
                if module in TsV2CatalogHandler.ta_volume_map:
                    vol = TsV2CatalogHandler.ta_volume_map[module]
                else:
                    # TRICKY: new modules added since the legacy ta won't have a volume in the map
                    print('WARNING: volume not found for {} while parsing link {}. Defaulting to vol1'.format(module, link[0]))
                    vol = 'vol1'
                new_link = ':{}:{}:{}:{}:{}'.format(lid, rid, vol, pid, module)


            content = content.replace(link[0], new_link)
        return content

    ta_volume_map = {
        "acceptable": "vol1",
        "accuracy_check": "vol1",
        "accurate": "vol1",
        "authority_level1": "vol1",
        "authority_level2": "vol1",
        "authority_level3": "vol1",
        "authority_process": "vol1",
        "church_leader_check": "vol1",
        "clear": "vol1",
        "community_evaluation": "vol1",
        "complete": "vol1",
        "goal_checking": "vol1",
        "good": "vol1",
        "important_term_check": "vol1",
        "intro_check": "vol1",
        "intro_checking": "vol1",
        "intro_levels": "vol1",
        "language_community_check": "vol1",
        "level1": "vol1",
        "level1_affirm": "vol1",
        "level2": "vol1",
        "level3": "vol1",
        "level3_approval": "vol1",
        "level3_questions": "vol1",
        "natural": "vol1",
        "other_methods": "vol1",
        "peer_check": "vol1",
        "self_assessment": "vol1",
        "self_check": "vol1",
        "finding_answers": "vol1",
        "gl_strategy": "vol1",
        "open_license": "vol1",
        "statement_of_faith": "vol1",
        "ta_intro": "vol1",
        "translation_guidelines": "vol1",
        "uw_intro": "vol1",
        "door43_translation": "vol1",
        "getting_started": "vol1",
        "intro_publishing": "vol1",
        "intro_share": "vol1",
        "platforms": "vol1",
        "prechecking_training": "vol1",
        "pretranslation_training": "vol1",
        "process_manual": "vol1",
        "publishing_prereqs": "vol1",
        "publishing_process": "vol1",
        "required_checking": "vol1",
        "setup_door43": "vol1",
        "setup_team": "vol1",
        "setup_tsandroid": "vol1",
        "setup_tsdesktop": "vol1",
        "setup_word": "vol1",
        "share_published": "vol1",
        "share_unpublished": "vol1",
        "tsandroid_translation": "vol1",
        "tsdesktop_translation": "vol1",
        "upload_merge": "vol1",
        "word_translation": "vol1",
        "tk_create": "vol1",
        "tk_enable": "vol1",
        "tk_find": "vol1",
        "tk_install": "vol1",
        "tk_intro": "vol1",
        "tk_start": "vol1",
        "tk_update": "vol1",
        "tk_use": "vol1",
        "translate_helpts": "vol1",
        "ts_create": "vol1",
        "ts_first": "vol1",
        "ts_install": "vol1",
        "ts_intro": "vol1",
        "ts_markverses": "vol1",
        "ts_navigate": "vol1",
        "ts_open": "vol1",
        "ts_problem": "vol1",
        "ts_publish": "vol1",
        "ts_request": "vol1",
        "ts_resources": "vol1",
        "ts_select": "vol1",
        "ts_settings": "vol1",
        "ts_share": "vol1",
        "ts_translate": "vol1",
        "ts_update": "vol1",
        "ts_upload": "vol1",
        "ts_useresources": "vol1",
        "uw_app": "vol1",
        "uw_audio": "vol1",
        "uw_checking": "vol1",
        "uw_first": "vol1",
        "uw_install": "vol1",
        "uw_language": "vol1",
        "uw_select": "vol1",
        "uw_update_content": "vol1",
        "choose_team": "vol1",
        "figs_events": "vol1",
        "figs_explicit": "vol1",
        "figs_explicitinfo": "vol1",
        "figs_hypo": "vol1",
        "figs_idiom": "vol1",
        "figs_intro": "vol1",
        "figs_irony": "vol1",
        "figs_metaphor": "vol1",
        "figs_order": "vol1",
        "figs_parables": "vol1",
        "figs_rquestion": "vol1",
        "figs_simile": "vol1",
        "figs_you": "vol1",
        "figs_youdual": "vol1",
        "figs_yousingular": "vol1",
        "file_formats": "vol1",
        "first_draft": "vol1",
        "guidelines_accurate": "vol1",
        "guidelines_church_approved": "vol1",
        "guidelines_clear": "vol1",
        "guidelines_intro": "vol1",
        "guidelines_natural": "vol1",
        "mast": "vol1",
        "qualifications": "vol1",
        "resources_intro": "vol1",
        "resources_links": "vol1",
        "resources_porp": "vol1",
        "resources_types": "vol1",
        "resources_words": "vol1",
        "translate_alphabet": "vol1",
        "translate_discover": "vol1",
        "translate_dynamic": "vol1",
        "translate_fandm": "vol1",
        "translate_form": "vol1",
        "translate_help": "vol1",
        "translate_levels": "vol1",
        "translate_literal": "vol1",
        "translate_manual": "vol1",
        "translate_names": "vol1",
        "translate_problem": "vol1",
        "translate_process": "vol1",
        "translate_retell": "vol1",
        "translate_source_licensing": "vol1",
        "translate_source_text": "vol1",
        "translate_source_version": "vol1",
        "translate_terms": "vol1",
        "translate_tform": "vol1",
        "translate_transliterate": "vol1",
        "translate_unknown": "vol1",
        "translate_wforw": "vol1",
        "translate_whatis": "vol1",
        "translate_why": "vol1",
        "translation_difficulty": "vol1",
        "writing_decisions": "vol1",
        "about_audio_recording": "vol2",
        "approach_to_audio": "vol2",
        "audio_acoustic_principles": "vol2",
        "audio_acoustical_treatments": "vol2",
        "audio_assessing_recording_space": "vol2",
        "audio_best_practices": "vol2",
        "audio_checklist_preparing_project": "vol2",
        "audio_checklist_recording_process": "vol2",
        "audio_checklists": "vol2",
        "audio_creating_new_file": "vol2",
        "audio_digital_recording_devices": "vol2",
        "audio_distribution": "vol2",
        "audio_distribution_amplification_recharging": "vol2",
        "audio_distribution_audio_player": "vol2",
        "audio_distribution_best_solutions": "vol2",
        "audio_distribution_door43": "vol2",
        "audio_distribution_license": "vol2",
        "audio_distribution_local": "vol2",
        "audio_distribution_microsd": "vol2",
        "audio_distribution_mobile_phone": "vol2",
        "audio_distribution_offline": "vol2",
        "audio_distribution_preparing_content": "vol2",
        "audio_distribution_radio": "vol2",
        "audio_distribution_wifi_hotspot": "vol2",
        "audio_editing": "vol2",
        "audio_editing_common_procedures": "vol2",
        "audio_editing_corrections": "vol2",
        "audio_editing_decisions_edit_rerecord": "vol2",
        "audio_editing_decisions_objective_subjective": "vol2",
        "audio_editing_finalizing": "vol2",
        "audio_editing_measuring_selection_length": "vol2",
        "audio_editing_modifying_pauses": "vol2",
        "audio_editing_navigating_timeline": "vol2",
        "audio_editing_using_your_ears": "vol2",
        "audio_equipment_overview": "vol2",
        "audio_equipment_setup": "vol2",
        "audio_field_environment": "vol2",
        "audio_guides": "vol2",
        "audio_guides_conversion_batch": "vol2",
        "audio_guides_normalizing": "vol2",
        "audio_guides_rename_batch": "vol2",
        "audio_interfaces": "vol2",
        "audio_introduction": "vol2",
        "audio_logistics": "vol2",
        "audio_managing_data": "vol2",
        "audio_managing_files": "vol2",
        "audio_managing_folders": "vol2",
        "audio_markers": "vol2",
        "audio_mic_activation": "vol2",
        "audio_mic_fine_tuning": "vol2",
        "audio_mic_gain_level": "vol2",
        "audio_mic_position": "vol2",
        "audio_mic_setup": "vol2",
        "audio_microphone": "vol2",
        "audio_noise_floor": "vol2",
        "audio_optimize_laptop": "vol2",
        "audio_playback_monitoring": "vol2",
        "audio_project_setup": "vol2",
        "audio_publishing_unfoldingword": "vol2",
        "audio_quality_standards": "vol2",
        "audio_recommended_accessories": "vol2",
        "audio_recommended_cables": "vol2",
        "audio_recommended_equipment": "vol2",
        "audio_recommended_headphones": "vol2",
        "audio_recommended_laptops": "vol2",
        "audio_recommended_mic_stands": "vol2",
        "audio_recommended_monitors": "vol2",
        "audio_recommended_playback_equipment": "vol2",
        "audio_recommended_pop_filters": "vol2",
        "audio_recommended_portable_recorders": "vol2",
        "audio_recommended_recording_devices": "vol2",
        "audio_recommended_tablets": "vol2",
        "audio_recording": "vol2",
        "audio_recording_environment": "vol2",
        "audio_recording_further_considerations": "vol2",
        "audio_recording_process": "vol2",
        "audio_setup_content": "vol2",
        "audio_setup_h2n": "vol2",
        "audio_setup_keyboard_shortcuts_audacity": "vol2",
        "audio_setup_keyboard_shortcuts_ocenaudio": "vol2",
        "audio_setup_ocenaudio": "vol2",
        "audio_setup_team": "vol2",
        "audio_signal_path": "vol2",
        "audio_signal_to_noise": "vol2",
        "audio_software": "vol2",
        "audio_software_file_renaming": "vol2",
        "audio_software_file_sharing": "vol2",
        "audio_software_format_conversion": "vol2",
        "audio_software_metadata_encoding": "vol2",
        "audio_software_recording_editing": "vol2",
        "audio_software_workspace": "vol2",
        "audio_standard_characteristics": "vol2",
        "audio_standard_file_naming": "vol2",
        "audio_standard_format": "vol2",
        "audio_standard_license": "vol2",
        "audio_standard_style": "vol2",
        "audio_studio_environment": "vol2",
        "audio_the_checker": "vol2",
        "audio_the_coordinator": "vol2",
        "audio_the_narrator": "vol2",
        "audio_the_recordist": "vol2",
        "audio_vision_purpose": "vol2",
        "audio_waveform_editor": "vol2",
        "audio_workspace_layout": "vol2",
        "excellence_in_audio": "vol2",
        "simplicity_in_audio": "vol2",
        "skills_training_in_audio": "vol2",
        "alphabet": "vol2",
        "formatting": "vol2",
        "headings": "vol2",
        "punctuation": "vol2",
        "spelling": "vol2",
        "verses": "vol2",
        "vol2_backtranslation": "vol2",
        "vol2_backtranslation_guidelines": "vol2",
        "vol2_backtranslation_kinds": "vol2",
        "vol2_backtranslation_purpose": "vol2",
        "vol2_backtranslation_who": "vol2",
        "vol2_backtranslation_written": "vol2",
        "vol2_intro": "vol2",
        "vol2_steps": "vol2",
        "vol2_things_to_check": "vol2",
        "check_notes": "vol2",
        "check_udb": "vol2",
        "check_ulb": "vol2",
        "gl_adaptulb": "vol2",
        "gl_done_checking": "vol2",
        "gl_notes": "vol2",
        "gl_questions": "vol2",
        "gl_translate": "vol2",
        "gl_udb": "vol2",
        "gl_ulb": "vol2",
        "gl_words": "vol2",
        "figs_123person": "vol2",
        "figs_abstractnouns": "vol2",
        "figs_activepassive": "vol2",
        "figs_apostrophe": "vol2",
        "figs_distinguish": "vol2",
        "figs_doublenegatives": "vol2",
        "figs_doublet": "vol2",
        "figs_ellipsis": "vol2",
        "figs_euphemism": "vol2",
        "figs_exclusive": "vol2",
        "figs_gendernotations": "vol2",
        "figs_genericnoun": "vol2",
        "figs_genitivecase": "vol2",
        "figs_go": "vol2",
        "figs_grammar": "vol2",
        "figs_hendiadys": "vol2",
        "figs_hyperbole": "vol2",
        "figs_inclusive": "vol2",
        "figs_informremind": "vol2",
        "figs_litotes": "vol2",
        "figs_merism": "vol2",
        "figs_metonymy": "vol2",
        "figs_parallelism": "vol2",
        "figs_partsofspeech": "vol2",
        "figs_personification": "vol2",
        "figs_pluralpronouns": "vol2",
        "figs_quotations": "vol2",
        "figs_rpronouns": "vol2",
        "figs_sentences": "vol2",
        "figs_singularpronouns": "vol2",
        "figs_synecdoche": "vol2",
        "figs_synonparallelism": "vol2",
        "figs_verbs": "vol2",
        "figs_youformal": "vol2",
        "guidelines_authoritative": "vol2",
        "guidelines_collaborative": "vol2",
        "guidelines_equal": "vol2",
        "guidelines_faithful": "vol2",
        "guidelines_historical": "vol2",
        "guidelines_ongoing": "vol2",
        "translate_bibleorg": "vol2",
        "translate_chapverse": "vol2",
        "translate_fraction": "vol2",
        "translate_manuscripts": "vol2",
        "translate_numbers": "vol2",
        "translate_ordinal": "vol2",
        "translate_original": "vol2",
        "translate_symaction": "vol2",
        "translate_textvariants": "vol2",
        "translate_versebridge": "vol2",
        "writing_background": "vol2",
        "writing_connectingwords": "vol2",
        "writing_intro": "vol2",
        "writing_newevent": "vol2",
        "writing_participants": "vol2",
        "writing_poetry": "vol2",
        "writing_proverbs": "vol2",
        "writing_quotations": "vol2",
        "writing_symlanguage": "vol2"
    }