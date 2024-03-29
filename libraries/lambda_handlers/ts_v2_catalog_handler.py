# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the tS v2 api.
#

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
import sys
import urlparse

import markdown
import yaml
import csv

from libraries.lambda_handlers.handler import Handler
from d43_aws_tools import S3Handler, DynamoDBHandler
from libraries.tools.file_utils import read_file, download_rc, remove, get_subdirs, remove_tree
from libraries.tools.legacy_utils import index_obs
from libraries.tools.url_utils import download_file, get_url, url_exists
from libraries.tools.ts_v2_utils import convert_rc_links, build_json_source_from_usx, make_legacy_date, \
    max_modified_date, get_rc_type, build_usx, prep_data_upload, date_is_older, max_long_modified_date, \
    get_project_from_manifest, index_chunks, tn_tsv_to_json

from libraries.lambda_handlers.instance_handler import InstanceHandler


class TsV2CatalogHandler(InstanceHandler):
    cdn_root_path = 'v2/ts'
    api_version = 'ts.2'

    def __init__(self, event, context, logger, **kwargs):
        super(TsV2CatalogHandler, self).__init__(event, context)

        self.ts_resource_cache = {}
        self.ts_languages_cache = {}
        self.ts_projects_cache = None
        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars').rstrip('/')
        self.from_email = self.retrieve(env_vars, 'from_email', 'Environment Vars')
        self.to_email = self.retrieve(env_vars, 'to_email', 'Environment Vars')
        self.logger = logger  # type: logging._loggerClass
        if 's3_handler' in kwargs:
            self.cdn_handler = kwargs['s3_handler']
        else:
            self.cdn_handler = S3Handler(self.cdn_bucket)  # pragma: no cover
        if 'dynamodb_handler' in kwargs:
            self.db_handler = kwargs['dynamodb_handler']
        else:
            self.db_handler = DynamoDBHandler('{}d43-catalog-status'.format(self.stage_prefix()))  # pragma: no cover
        if 'url_handler' in kwargs:
            self.get_url = kwargs['url_handler']
        else:
            self.get_url = get_url  # pragma: no cover
        if 'download_handler' in kwargs:
            self.download_file = kwargs['download_handler']
        else:
            self.download_file = download_file  # pragma: no cover
        if 'url_exists_handler' in kwargs:
            self.url_exists = kwargs['url_exists_handler']
        else:
            self.url_exists = url_exists  # pragma: no cover

        self.temp_dir = tempfile.mkdtemp('', 'tsv2', None)

    def __del__(self):
        try:
            shutil.rmtree(self.temp_dir)
        finally:
            pass

    def _run(self):
        """
        Generates the v2 catalog
        :return:
        """
        try:
            self.logger.debug('Temp directory {} contents {}'.format('/tmp', get_subdirs('/tmp/')))
            return self.__execute()
        except Exception as e:
            self.report_error(e.message)
            raise Exception, Exception(e), sys.exc_info()[2]

    def __execute(self):
        cat_keys = []
        cat_dict = {}
        supplemental_resources = []

        result = self._get_status()
        if not result:
            return False
        else:
            (self.status, source_status) = result

        # check if build is complete
        if self.status['state'] == 'complete':
            self.logger.debug('Catalog already generated')
            return True

        if self.status['state'] == 'aborted':
            self.logger.debug('Catalog generation was aborted')
            return True

        # retrieve the latest catalog
        catalog_content = self.get_url(source_status['catalog_url'], True)
        if not catalog_content:
            self.logger.error("{0} does not exist".format(source_status['catalog_url']))
            return False
        try:
            self.latest_catalog = json.loads(catalog_content)
        except Exception as e:
            self.logger.error("Failed to load the catalog json: {0}".format(e))
            return False

        # walk v3 catalog
        for lang in self.latest_catalog['languages']:
            lid = TsV2CatalogHandler.sanitize_identifier(lang['identifier'], lower=False)
            # DEBUG
            # if lid != 'hi':
            #     continue
            self.logger.info('Inspecting {}'.format(lid))
            for res in lang['resources']:
                rid = TsV2CatalogHandler.sanitize_identifier(res['identifier'])
                self.logger.info('Inspecting {}_{}'.format(lid, rid))

                rc_format = None

                self.logger.debug('Temp directory {} contents {}'.format(self.temp_dir, get_subdirs(self.temp_dir)))
                res_temp_dir = os.path.join(self.temp_dir, lid, rid)
                os.makedirs(res_temp_dir)

                if 'formats' in res:
                    for format in res['formats']:
                        finished_processes = {}
                        if not rc_format and get_rc_type(format):
                            # locate rc_format (for multi-project RCs)
                            rc_format = format

                        self._process_usfm(lid, rid, res, format, res_temp_dir)

                        # TRICKY: bible notes and questions are in the resource
                        if rid != 'obs':
                            process_id = '_'.join([lid, rid, 'notes'])
                            if process_id not in self.status['processed']:
                                tn = self._index_note_files(lid, rid, res, format, process_id, res_temp_dir)
                                if tn:
                                    self._upload_all(tn)
                                    finished_processes[process_id] = tn.keys()
                                    cat_keys = cat_keys + tn.keys()
                            else:
                                cat_keys = cat_keys + self.status['processed'][process_id]

                            process_id = '_'.join([lid, rid, 'questions'])
                            if process_id not in self.status['processed']:
                                tq = self._index_question_files(lid, rid, res, format, process_id, res_temp_dir)
                                if tq:
                                    self._upload_all(tq)
                                    finished_processes[process_id] = tq.keys()
                                    cat_keys = cat_keys + tq.keys()
                            else:
                                cat_keys = cat_keys + self.status['processed'][process_id]

                        # TRICKY: update the finished processes once per format to limit db hits
                        if finished_processes:
                            self.status['processed'].update(finished_processes)
                            self._set_status()

                for project in res['projects']:
                    pid = TsV2CatalogHandler.sanitize_identifier(project['identifier'])
                    # DEBUG
                    # if pid != 'tit' and rid != 'tw':
                    #     continue
                    if 'formats' in project:
                        for format in project['formats']:
                            finished_processes = {}
                            if not rc_format and get_rc_type(format):
                                # locate rc_format (for single-project RCs)
                                rc_format = format

                            # TRICKY: there should only be a single tW for each language
                            process_id = '_'.join([lid, 'words'])
                            if process_id not in self.status['processed']:
                                tw = self._index_words_files(lid, rid, res, format, process_id, res_temp_dir)
                                if tw:
                                    self._upload_all(tw)
                                    finished_processes[process_id] = tw.keys()
                                    cat_keys = cat_keys + tw.keys()
                            else:
                                cat_keys = cat_keys + self.status['processed'][process_id]

                            if rid == 'obs':
                                process_id = '_'.join([lid, rid, pid])
                                if process_id not in self.status['processed']:
                                    if self._has_resource_changed('obs', lid, rid, format['modified']):
                                        self.logger.info('Processing {}'.format(process_id))
                                        obs_json = index_obs(lid, rid, format, res_temp_dir, self.download_file)
                                        upload = prep_data_upload(
                                            '{}/{}/{}/v{}/source.json'.format(pid, lid, rid, res['version']),
                                            obs_json, res_temp_dir)
                                        self._upload(upload)
                                    else:
                                        self.logger.debug(
                                            'Skipping OBS {0}-{1} because it hasn\'t changed'.format(lid, rid))
                                    finished_processes[process_id] = []
                                else:
                                    cat_keys = cat_keys + self.status['processed'][process_id]

                            # TRICKY: obs notes and questions are in the project
                            process_id = '_'.join([lid, rid, pid, 'notes'])
                            if process_id not in self.status['processed']:
                                tn = self._index_note_files(lid, rid, res, format, process_id, res_temp_dir)
                                if tn:
                                    self._upload_all(tn)
                                    finished_processes[process_id] = tn.keys()
                                    cat_keys = cat_keys + tn.keys()
                            else:
                                cat_keys = cat_keys + self.status['processed'][process_id]

                            process_id = '_'.join([lid, rid, pid, 'questions'])
                            if process_id not in self.status['processed']:
                                tq = self._index_question_files(lid, rid, res, format, process_id, res_temp_dir)
                                if tq:
                                    self._upload_all(tq)
                                    finished_processes[process_id] = tq.keys()
                                    cat_keys = cat_keys + tq.keys()
                            else:
                                cat_keys = cat_keys + self.status['processed'][process_id]

                            # TRICKY: update the finished processes once per format to limit db hits
                            if finished_processes:
                                self.status['processed'].update(finished_processes)
                                self._set_status()

                    if not rc_format:
                        raise Exception('Could not find a format for {}_{}_{}'.format(lid, rid, pid))

                    modified = make_legacy_date(rc_format['modified'])
                    long_modified = rc_format['modified']
                    rc_type = get_rc_type(rc_format)

                    if modified is None:
                        modified = time.strftime('%Y%m%d')
                        self.logger.warning('Could not find date modified for {}_{}_{} from "{}"'.format(lid, rid, pid,
                                                                                                         rc_format[
                                                                                                             'modified']))
                    if long_modified is None:
                        long_modified = modified

                    if rc_type == 'book' or rc_type == 'bundle':
                        self._build_catalog_node(cat_dict, lang, res, project, modified, long_modified)
                    else:
                        # store supplementary resources for processing after catalog nodes have been fully built
                        supplemental_resources.append({
                            'language': lang,
                            'resource': res,
                            'project': project,
                            'modified': modified,
                            'long_modified': long_modified,
                            'rc_type': rc_type
                        })

                # cleanup resource directory
                remove_tree(res_temp_dir)
            # cleanup language directory
            remove_tree(os.path.join(self.temp_dir, lid))
        # inject supplementary resources
        for s in supplemental_resources:
            self._add_supplement(cat_dict, s['language'], s['resource'], s['project'], s['modified'], s['rc_type'])

        api_uploads = []

        # normalize catalog nodes
        root_cat = []
        for pid in cat_dict:
            project = cat_dict[pid]
            lang_cat = []
            for lid in project['_langs']:
                lang = project['_langs'][lid]
                res_cat = []
                for rid in lang['_res']:
                    res = lang['_res'][rid]

                    # disable missing catalogs

                    # disable tN
                    if '_'.join([lid, '*', pid, 'tn']) not in cat_keys:
                        res['notes'] = ''

                    # disable tQ
                    if '_'.join([lid, '*', pid, 'tq']) not in cat_keys:
                        res['checking_questions'] = ''

                    # disable tW
                    if '_'.join([lid, '*', '*', 'tw']) not in cat_keys:
                        res['terms'] = ''

                    res_cat.append(res)
                # TODO: what is this?
                api_uploads.append(prep_data_upload('{}/{}/resources.json'.format(pid, lid), res_cat, self.temp_dir))

                del lang['_res']
                if ('project' in lang):
                    # skip empty artifacts
                    lang_cat.append(lang)
                else:
                    self.logger.warning('Excluding empty language artifact in {}'.format(pid))
            api_uploads.append(prep_data_upload('{}/languages.json'.format(pid), lang_cat, self.temp_dir))

            del project['_langs']
            if len(lang_cat) != 0:
                root_cat.append(project)
        catalog_upload = prep_data_upload('catalog.json', root_cat, self.temp_dir)
        api_uploads.append(catalog_upload)
        # TRICKY: also upload to legacy path for backwards compatibility
        api_uploads.append({
            'key': '/ts/txt/2/catalog.json',
            'path': catalog_upload['path']
        })

        # upload files
        for upload in api_uploads:
            if not upload['key'].startswith('/'):
                key = '{}/{}'.format(TsV2CatalogHandler.cdn_root_path, upload['key'])
            else:
                key = upload['key'].lstrip('/')
            self.cdn_handler.upload_file(upload['path'], key)

        self.status['state'] = 'complete'
        self._set_status()

    def _set_status(self):
        """
        Records the status after checking if the status is still valid
        because we might have manually changed it.
        If the status is "aborted" this will raise an exception
        :return:
        """
        result = self._get_status()
        if result and result[0]['state'] == 'aborted':
            raise Exception("Aborted because the status flag is set to 'aborted' in dynamodb")

        # record the status
        self.status['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db_handler.update_item({'api_version': TsV2CatalogHandler.api_version}, self.status)

    def _has_resource_changed(self, pid, lid, rid, modified_at):
        """
        Checks if a resource has changed.
        The resource is considered changed if the modified_at value is newer than what's found in the tS catalog.
        :param lid:
        :param rid:
        :param pid:
        :param modified_at:
        :return:
        """
        # Check the language first
        # TODO: this is dangerous, because it could accidentally hide resources that have
        #  been updated, but are not the most recent within the language or project.
        #  This would occur if content is created offline, then pushed out of order of creation.
        if not self._has_language_changed(pid, lid, modified_at):
            return False

        # look up the existing resources entry
        cache_key = '{0}--{1}'.format(pid, lid)
        if cache_key in self.ts_resource_cache:
            ts_resources = self.ts_resource_cache[cache_key]
        else:
            ts_resources = self.get_url('https://cdn.door43.org/v2/ts/{0}/{1}/resources.json'.format(pid, lid), True)
            if ts_resources:
                self.ts_resource_cache[cache_key] = ts_resources

        if not ts_resources:
            return False
        try:
            resources = json.loads(ts_resources)
        except:
            return False

        # check if the resource has been modified
        for res in resources:
            # TRICKY: tn, tq, and tw are all the same across all resources in the same language and book.
            #  so we can use the first available resource
            if rid == 'tn' or rid == 'obs-tn':
                if res['notes']:
                    m = self._get_url_date_modified(res['notes'])
                    return date_is_older(m, modified_at)
                else:
                    return True
            elif rid == 'tq' or rid == 'obs-tq':
                if res['checking_questions']:
                    m = self._get_url_date_modified(res['checking_questions'])
                    return date_is_older(m, modified_at)
                else:
                    return True
            elif rid == 'tw':
                if res['terms']:
                    m = self._get_url_date_modified(res['terms'])
                    return date_is_older(m, modified_at)
                else:
                    return True
            elif res['slug'] != rid:
                continue
            # perform a standard date check with the source
            if 'long_date_modified' in res:
                return date_is_older(res['long_date_modified'], modified_at)
            else:
                # backwards compatibility
                return date_is_older(res['date_modified'], make_legacy_date(modified_at))

    def _get_url_date_modified(self, url_string):
        try:
            url = urlparse.urlparse(url_string)
            value = urlparse.parse_qs(url.query)['date_modified']
            if len(value) > 0:
                return value[0]
            else:
                # just some default old date
                return '19990101'
        except:
            # just some default old date
            return '19990101'

    def _has_language_changed(self, pid, lid, modified_at):
        """
        Checks if a language has changed.
        The project is considered changed if the modified_at value is newer than what's found in the tS catalog.
        :param lid:
        :param rid:
        :param pid:
        :param modified_at:
        :return:
        """
        if not self._has_project_changed(pid, modified_at):
            return False

        # look up the existing language entry
        cache_key = pid
        if cache_key in self.ts_languages_cache:
            ts_languages = self.ts_languages_cache[cache_key]
        else:
            ts_languages = self.get_url('https://cdn.door43.org/v2/ts/{0}/languages.json'.format(pid), True)
            if ts_languages:
                self.ts_languages_cache[cache_key] = ts_languages

        if not ts_languages:
            return False
        try:
            languages = json.loads(ts_languages)
        except:
            return False

        # check if the resource has been modified
        for lang in languages:
            if lang['language']['slug'] != lid:
                continue
            if 'long_date_modified' in lang['language']:
                return date_is_older(lang['language']['long_date_modified'], modified_at)
            else:
                # backwards compatibility
                return date_is_older(lang['language']['date_modified'], make_legacy_date(modified_at))

    def _has_project_changed(self, pid, modified_at):
        """
        Checks if a project has changed.
        The project is considered changed if the modified_at value is newer than what's found in the tS catalog.
        :param pid:
        :param modified_at:
        :return:
        """
        # look up the existing project entry
        if not self.ts_projects_cache:
            self.ts_projects_cache = self.get_url('https://cdn.door43.org/v2/ts/catalog.json', True)

        if not self.ts_projects_cache:
            # The cache could not be built, so automatically consider changed
            return True
        try:
            projects = json.loads(self.ts_projects_cache)
        except:
            return False

        # check if the resource has been modified
        for p in projects:
            if p['slug'] != pid:
                continue
            if 'long_date_modified' in p:
                return date_is_older(p['long_date_modified'], modified_at)
            else:
                # backwards compatibility
                return date_is_older(p['date_modified'], make_legacy_date(modified_at))

    def _get_status(self):
        """
        Retrieves the catalog status from AWS or generates a new status object

        :return: A tuple containing the status object of the target and source catalogs, or False if the source is not ready
        """
        status_results = self.db_handler.query_items({
            'api_version': {
                'condition': 'is_in',
                'value': ['3', TsV2CatalogHandler.api_version]
            }
        })
        source_status = None
        status = None
        for s in status_results:
            if s['api_version'] == '3':
                source_status = s
            elif s['api_version'] == TsV2CatalogHandler.api_version:
                status = s
        if not source_status:
            self.logger.warning('Source catalog status not found')
            return False
        if source_status['state'] != 'complete':
            self.logger.debug('Source catalog is not ready for use')
            return False
        if not status or ((status['source_timestamp'] != source_status['timestamp']) and status['state'] != 'in-progress'):
            # begin or restart process.
            # If the catalog is already being generated it will be allowed to finish before re-starting.
            status = {
                'api_version': TsV2CatalogHandler.api_version,
                'catalog_url': '{}/ts/txt/2/catalog.json'.format(self.cdn_url),
                'source_api': source_status['api_version'],
                'source_timestamp': source_status['timestamp'],
                'state': 'in-progress',
                'processed': {}
            }

        return (status, source_status)

    def _index_note_files(self, lid, rid, resource, format, process_id, temp_dir):
        """

        :param lid:
        :param rid:
        :param format:
        :return: a dictionary of notes to upload
        """
        tn_uploads = {}

        format_str = format['format']
        if (rid == 'obs-tn' or rid == 'tn') and 'type=help' in format_str:
            self.logger.debug('Inspecting notes {}'.format(process_id))

            content_format = format['format']
            if 'content=text/markdown' in content_format:
                tn_uploads = self._tn_md_to_json_file(lid, rid, resource, format, temp_dir)
            elif 'content=text/tsv' in content_format:
                tn_uploads = self._tn_tsv_to_json_file(lid, rid, resource, format, temp_dir)
            else:
                self.report_error("Unsupported content type '{}' found in {}".format(content_format, format['url']))
                raise Exception("Unsupported content type '{}' found in {}".format(content_format, format['url']))

        return tn_uploads


    def _tn_tsv_to_json_file(self, lid, rid, resource, format, temp_dir):
        """
        Converts a tsv tN to json
        This will write a bunch of files and return a list of files to be uploaded.

        Chunk definitions will be used to validate the note organization.

        :param lid: the language id of the notes
        :param temp_dir: the directory where all the files will be written
        :return: a list of note files to upload
        """
        rc_dir = None
        tn_uploads = {}

        for project in resource['projects']:
            pid = Handler.sanitize_identifier(project['identifier'])

            # skip re-processing notes that have not changed
            if not self._has_resource_changed(pid, lid, rid, format['modified']):
                self.logger.debug('Skipping notes {0}-{1}-{2} because it hasn\'t changed'.format(lid, rid, pid))
                continue

            self.logger.info('Processing notes {}-{}-{}'.format(lid, rid, pid))

            # download RC if not already
            if rc_dir is None:
                rc_dir = download_rc(lid, rid, format['url'], temp_dir, self.download_file)
            if not rc_dir:
                break

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            dc = manifest['dublin_core']
            project_path = get_project_from_manifest(manifest, project['identifier'])['path']

            chunks = []

            # verify project file exists
            note_file = os.path.normpath(os.path.join(rc_dir, project_path))
            if not os.path.exists(note_file):
                raise Exception('Could not find translationNotes file at {}'.format(note_file))

            # collect chunk data
            if pid != 'obs':
                try:
                    data = get_url('https://cdn.door43.org/bible/txt/1/{}/chunks.json'.format(pid))
                    chunks = index_chunks(json.loads(data))
                except:
                    self.report_error('Failed to retrieve chunk information for {}-{}'.format(lid, pid))
                    continue

            # convert
            with open(note_file, 'rb') as tsvin:
                tsv = csv.DictReader(tsvin, dialect='excel-tab')
                note_json = tn_tsv_to_json(tsv, chunks)

            if note_json:
                tn_key = '_'.join([lid, '*', pid, 'tn'])
                note_json.append({'date_modified': dc['modified'].replace('-', '')})
                note_upload = prep_data_upload('{}/{}/notes.json'.format(pid, lid), note_json, temp_dir)
                tn_uploads[tn_key] = note_upload

        try:
            remove_tree(rc_dir, True)
        except:
            pass

        return tn_uploads


    def _tn_md_to_json_file(self, lid, rid, resource, format, temp_dir):
        """
        Converts a markdown tN to json
        This will write a bunch of files and return a list of files to be uploaded.

        Chunk definitions will be used to validate the note organization.

        :param lid: the language id of the notes
        :param temp_dir: the directory where all the files will be written
        :param rc_dir: the directory of the resource container
        :param manifest: the rc manifest data
        :param reporter: a lambda handler used for reporting
        :type reporter: Handler
        :return: a list of note files to upload
        """
        rc_dir = None
        # dc = manifest['dublin_core']
        note_general_re = re.compile('^([^#]+)', re.UNICODE)
        note_re = re.compile('^#+([^#\n]+)#*([^#]*)', re.UNICODE | re.MULTILINE | re.DOTALL)
        tn_uploads = {}

        for project in resource['projects']:
            pid = Handler.sanitize_identifier(project['identifier'])

            # skip re-processing notes that have not changed
            if not self._has_resource_changed(pid, lid, rid, format['modified']):
                self.logger.debug('Skipping notes {0}-{1}-{2} because it hasn\'t changed'.format(lid, rid, pid))
                continue

            self.logger.info('Processing notes {}-{}-{}'.format(lid, rid, pid))

            # download RC if not already
            if rc_dir is None:
                rc_dir = download_rc(lid, rid, format['url'], temp_dir, self.download_file)
            if not rc_dir:
                break

            manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            dc = manifest['dublin_core']
            project_path = get_project_from_manifest(manifest, project['identifier'])['path']

            chunk_json = []
            if pid != 'obs':
                try:
                    data = get_url('https://cdn.door43.org/bible/txt/1/{}/chunks.json'.format(pid))
                    chunk_json = index_chunks(json.loads(data))
                except:
                    self.report_error('Failed to retrieve chunk information for {}-{}'.format(lid, pid))
                    continue

            note_dir = os.path.normpath(os.path.join(rc_dir, project_path))
            note_json = []
            if not os.path.exists(note_dir):
                raise Exception('Could not find translationNotes directory at {}'.format(note_dir))
            chapters = os.listdir(note_dir)

            for chapter in chapters:
                if chapter in ['.', '..', 'front', '.DS_Store']:
                    continue
                chapter_dir = os.path.join(note_dir, chapter)
                verses = os.listdir(chapter_dir)
                verses.sort()

                notes = []
                firstvs = None
                note_hashes = []
                for verse in verses:
                    if verse in ['.', '..', 'intro.md', '.DS_Store']:
                        continue

                    # notes = []
                    verse_file = os.path.join(chapter_dir, verse)
                    verse = verse.split('.')[0]
                    try:
                        verse_body = read_file(verse_file)
                    except Exception as e:
                        self.report_error('Failed to read file {}'.format(verse_file))
                        raise e

                    general_notes = note_general_re.search(verse_body)

                    # zero pad chapter to match chunking scheme
                    padded_chapter = chapter
                    while len(padded_chapter) < 3 and padded_chapter not in chunk_json:
                        padded_chapter = padded_chapter.zfill(len(padded_chapter) + 1)
                        # keep padding if match is found
                        if padded_chapter in chunk_json:
                            chapter = padded_chapter

                    # validate chapters
                    if pid != 'obs' and chapter not in chunk_json:
                        raise Exception(
                            'Missing chapter "{}" key in chunk json while reading chunks for {}. RC: {}'.format(chapter,
                                                                                                                pid,
                                                                                                                rc_dir))

                    # zero pad verse to match chunking scheme
                    padded_verse = verse
                    while len(padded_verse) < 3 and chapter in chunk_json and padded_verse not in chunk_json[chapter]:
                        padded_verse = padded_verse.zfill(len(padded_verse) + 1)
                        # keep padding if match is found
                        if padded_verse in chunk_json[chapter]:
                            verse = padded_verse

                    # close chunk
                    chapter_key = chapter
                    if firstvs is not None and (pid != 'obs' and chapter_key not in chunk_json):
                        # attempt to recover if Psalms
                        if pid == 'psa':
                            chapter_key = chapter_key.zfill(3)
                        else:
                            self.report_error(
                                    'Could not find chunk data for {} {} {}'.format(rc_dir, pid, chapter_key))

                    if firstvs is not None and (pid == 'obs' or verse in chunk_json[chapter_key]):
                        note_json.append({
                            'id': '{}-{}'.format(chapter, firstvs),
                            'tn': notes
                        })
                        firstvs = verse
                        notes = []
                    elif firstvs is None:
                        firstvs = verse

                    if general_notes:
                        verse_body = note_general_re.sub('', verse_body)
                        notes.append({
                            'ref': 'General Information',
                            'text': general_notes.group(0).strip()
                        })

                    for note in note_re.findall(verse_body):
                        # TRICKY: do not include translation words in the list of notes
                        if note[0].strip().lower() != 'translationwords':
                            hasher = hashlib.md5()
                            hasher.update(note[0].strip().lower().encode('utf-8'))
                            note_hash = hasher.hexdigest()
                            if note_hash not in note_hashes:
                                note_hashes.append(note_hash)
                                notes.append({
                                    'ref': note[0].strip(),
                                    'text': note[1].strip()
                                })

                # close last chunk
                if firstvs is not None:
                    note_json.append({
                        'id': '{}-{}'.format(chapter, firstvs),
                        'tn': notes
                    })

            if note_json:
                tn_key = '_'.join([lid, '*', pid, 'tn'])
                note_json.append({'date_modified': dc['modified'].replace('-', '')})
                note_upload = prep_data_upload('{}/{}/notes.json'.format(pid, lid), note_json, temp_dir)
                tn_uploads[tn_key] = note_upload

        try:
            remove_tree(rc_dir, True)
        except:
            pass

        return tn_uploads

    def _index_question_files(self, lid, rid, resource, format, process_id, temp_dir):
        question_re = re.compile('^#+([^#\n]+)#*([^#]*)', re.UNICODE | re.MULTILINE | re.DOTALL)
        tq_uploads = {}

        format_str = format['format']
        if (rid == 'obs-tq' or rid == 'tq') and 'type=help' in format_str:
            self.logger.debug('Inspecting questions {}'.format(process_id))
            rc_dir = None

            for project in resource['projects']:
                pid = TsV2CatalogHandler.sanitize_identifier(project['identifier'])

                # skip re-processing notes that have not changed
                if not self._has_resource_changed(pid, lid, rid, format['modified']):
                    self.logger.debug('Skipping questions {0}-{1}-{2} because it hasn\'t changed'.format(lid, rid, pid))
                    continue

                self.logger.info('Processing questions {}-{}-{}'.format(lid, rid, pid))

                # download RC if not already
                if rc_dir is None:
                    rc_dir = download_rc(lid, rid, format['url'], temp_dir, self.download_file)
                if not rc_dir:
                    break

                manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
                dc = manifest['dublin_core']
                project_path = get_project_from_manifest(manifest, project['identifier'])['path']

                question_dir = os.path.normpath(os.path.join(rc_dir, project_path))
                question_json = []

                if not os.path.isdir(question_dir):
                    self.logger.warning('Missing directory at {}. Is the manifest out of date?'.format(question_dir))
                    continue

                chapters = os.listdir(question_dir)
                for chapter in chapters:
                    if chapter in ['.', '..']: continue
                    unique_questions = {}
                    chapter_dir = os.path.join(question_dir, chapter)
                    chunks = os.listdir(chapter_dir)
                    for chunk in chunks:
                        if chunk in ['.', '..']: continue
                        chunk_file = os.path.join(chapter_dir, chunk)
                        chunk = chunk.split('.')[0]
                        chunk_body = read_file(chunk_file)

                        for question in question_re.findall(chunk_body):
                            hasher = hashlib.md5()
                            hasher.update(question[1].strip().encode('utf-8'))
                            question_hash = hasher.hexdigest()
                            if question_hash not in unique_questions:
                                # insert unique question
                                unique_questions[question_hash] = {
                                    'q': question[0].strip(),
                                    'a': question[1].strip(),
                                    'ref': [
                                        u'{}-{}'.format(chapter, chunk)
                                    ]
                                }
                            else:
                                # append new reference
                                unique_questions[question_hash]['ref'].append('{}-{}'.format(chapter, chunk))

                    question_array = []
                    for hash in unique_questions:
                        question_array.append(unique_questions[hash])
                    if question_array:
                        question_json.append({
                            'id': chapter,
                            'cq': question_array
                        })

                if question_json:
                    tq_key = '_'.join([lid, '*', pid, 'tq'])
                    question_json.append({'date_modified': dc['modified'].replace('-', '')})
                    upload = prep_data_upload('{}/{}/questions.json'.format(pid, lid), question_json, temp_dir)
                    tq_uploads[tq_key] = upload

            try:
                remove_tree(rc_dir, True)
            except:
                pass
        return tq_uploads

    def _index_words_files(self, lid, rid, resource, format, process_id, temp_dir):
        """
        Returns an array of markdown files found in a tW dictionary
        :param lid:
        :param rid:
        :param format:
        :return:
        """
        word_title_re = re.compile('^#([^#\n]*)#*', re.UNICODE)
        h2_re = re.compile('^##([^#\n]*)#*', re.UNICODE)
        obs_example_re = re.compile('\_*\[([^\[\]]+)\]\(([^\(\)]+)\)_*(.*)', re.UNICODE | re.IGNORECASE)
        block_re = re.compile('^##', re.MULTILINE | re.UNICODE)
        word_links_re = re.compile('\[([^\[\]]+)\]\(\.\.\/(kt|other)\/([^\(\)]+)\.md\)', re.UNICODE | re.IGNORECASE)
        ta_html_re = re.compile('(<a\s+href="(:[a-z-_0-9]+:ta:vol\d:[a-z-\_]+:[a-z-\_]+)"\s*>([^<]+)<\/a>)',
                                re.UNICODE | re.IGNORECASE)

        words = []
        words_date_modified = None
        format_str = format['format']
        if rid == 'tw' and 'type=dict' in format_str:
            rc_dir = None

            # TRICKY: there should only be one project
            for project in resource['projects']:
                pid = TsV2CatalogHandler.sanitize_identifier(project['identifier'])

                # skip re-processing words that have not changed
                if not self._has_resource_changed(pid, lid, rid, format['modified']):
                    self.logger.debug('Skipping words {} because it hasn\'t changed'.format(process_id))
                    continue

                self.logger.info('Processing words {}-{}-{}'.format(lid, rid, pid))

                # download RC if not already
                if rc_dir is None:
                    rc_dir = download_rc(lid, rid, format['url'], temp_dir, self.download_file)
                if not rc_dir:
                    break

                manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
                dc = manifest['dublin_core']
                words_date_modified = dc['modified'].replace('-', '').split('T')[0]
                project_path = get_project_from_manifest(manifest, project['identifier'])['path']

                content_dir = os.path.normpath(os.path.join(rc_dir, project_path))
                categories = os.listdir(content_dir)
                for cat in categories:
                    if cat in ['.', '..']: continue
                    cat_dir = os.path.join(content_dir, cat)
                    if not os.path.isdir(cat_dir): continue
                    word_files = os.listdir(cat_dir)
                    for word in word_files:
                        if word in ['.', '..', '.DS_Store']: continue
                        word_path = os.path.join(cat_dir, word)
                        word_id = word.split('.md')[0]
                        try:
                            word_content = read_file(word_path)
                        except Exception as e:
                            self.report_error(u'Failed to read file {}: {}'.format(word_path, e.message))
                            raise

                        # TRICKY: the title is always at the top
                        title_match = word_title_re.match(word_content)
                        if title_match:
                            title = title_match.group(1)
                        else:
                            self.report_error('missing title in {}'.format(word_path))
                            continue
                        word_content = word_title_re.sub('', word_content).strip()

                        # TRICKY: the definition title is always after the title
                        def_title = ''
                        def_title_match = h2_re.match(word_content)
                        if def_title_match:
                            def_title = def_title_match.group(1).strip()
                            word_content = h2_re.sub('', word_content).strip()
                        else:
                            self.report_error('missing definition title in {}'.format(word_path))

                        # find obs examples
                        blocks = block_re.split(word_content)
                        cleaned_blocks = []
                        examples = []
                        for block in blocks:
                            if 'examples from the bible stories' in block.lower():
                                for link in obs_example_re.findall(block):
                                    if 'obs' not in link[1]:
                                        self.logger.error(u'non-obs link found in passage examples: {}'.format(link[1]))
                                    else:
                                        examples.append({
                                            'ref': link[0].replace(':', '-'),
                                            'text': markdown.markdown(link[2].strip())
                                        })
                            else:
                                cleaned_blocks.append(block)
                        word_content = '##'.join(cleaned_blocks)

                        # find all tW links and use them in related words
                        related_words = [w[2] for w in word_links_re.findall(word_content)]

                        # convert links to legacy form. TODO: we should convert links after converting to html so we don't have to do it twice.
                        word_content = convert_rc_links(word_content)
                        word_content = markdown.markdown(word_content)
                        # convert html links back to dokuwiki links
                        # TRICKY: we converted the ta urls, but now we need to format them as dokuwiki links
                        # e.g. [[en:ta:vol1:translate:translate_unknown | How to Translate Unknowns]]
                        for ta_link in ta_html_re.findall(word_content):
                            new_link = u'[[{} | {}]]'.format(ta_link[1], ta_link[2])
                            word_content = word_content.replace(ta_link[0], new_link)

                        words.append({
                            'aliases': [a.strip() for a in title.split(',') if
                                        a.strip() != word_id and a.strip() != title.strip()],
                            'cf': related_words,
                            'def': word_content,
                            'def_title': def_title.rstrip(':'),
                            'ex': examples,
                            'id': word_id,
                            'sub': '',
                            'term': title.strip()
                        })

            try:
                remove_tree(rc_dir, True)
            except:
                pass

            if words:
                words.append({
                    'date_modified': words_date_modified
                })
                upload = prep_data_upload('bible/{}/words.json'.format(lid), words, temp_dir)
                return {
                    '_'.join([lid, '*', '*', 'tw']): upload
                }
        return {}

    def _process_usfm(self, lid, rid, resource, format, temp_dir):
        """
        Converts a USFM bundle into usx, loads the data into json and uploads it.
        Returns an array of usx file paths.
        :param lid:
        :param rid:
        :param format:
        :return: an array of json blobs
        """

        format_str = format['format']
        if 'application/zip' in format_str and 'usfm' in format_str:
            rc_dir = None
            # rc_dir = download_rc(lid, rid, format['url'], temp_dir, self.download_file)
            # if not rc_dir: return

            # manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
            # usx_dir = os.path.join(rc_dir, 'usx')
            for project in resource['projects']:
                pid = TsV2CatalogHandler.sanitize_identifier(project['identifier'])
                # DEBUG
                # if pid != 'tit':
                #     continue
                process_id = '_'.join([lid, rid, pid])

                if process_id not in self.status['processed']:
                    # skip re-processing projects that have not changed
                    if not self._has_resource_changed(pid, lid, rid, format['modified']):
                        self.status['processed'][process_id] = []
                        self._set_status()
                        self.logger.debug('Skipping {0}-{1}-{2} because it hasn\'t changed'.format(lid, rid, pid))
                        continue

                    self.logger.info('Processing usfm for {}'.format(process_id))

                    # download RC if not already
                    if rc_dir is None:
                        rc_dir = download_rc(lid, rid, format['url'], temp_dir, self.download_file)
                    if not rc_dir:
                        break

                    manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
                    usx_dir = os.path.join(rc_dir, 'usx')
                    project_path = get_project_from_manifest(manifest, project['identifier'])['path']

                    # copy usfm project file
                    usfm_dir = os.path.join(temp_dir, '{}_usfm'.format(process_id))
                    if not os.path.exists(usfm_dir):
                        os.makedirs(usfm_dir)
                    usfm_dest_file = os.path.normpath(os.path.join(usfm_dir, project_path))
                    usfm_src_file = os.path.normpath(os.path.join(rc_dir, project_path))
                    shutil.copyfile(usfm_src_file, usfm_dest_file)

                    # transform usfm to usx
                    try:
                        build_usx(usfm_dir, usx_dir)
                    except Exception as e:
                        self.report_error('Failed to generate usx for {}'.format(process_id))
                        raise e

                    # clean up converted usfm file
                    remove(usfm_dest_file, True)

                    # convert USX to JSON
                    path = os.path.normpath(os.path.join(usx_dir, '{}.usx'.format(pid.upper())))
                    source = build_json_source_from_usx(path, lid, pid, format['modified'], self)
                    upload = prep_data_upload('{}/{}/{}/v{}/source.json'.format(pid, lid, rid, resource['version']),
                                              source['source'], temp_dir)
                    self.cdn_handler.upload_file(upload['path'],
                                                 '{}/{}'.format(TsV2CatalogHandler.cdn_root_path, upload['key']))

                    self.status['processed'][process_id] = []
                    self._set_status()
            # clean up download
            try:
                remove_tree(rc_dir, True)
            except:
                pass

    def _upload_all(self, uploads):
        """
        Uploads an array or object of uploads
        :param uploads:
        :return:
        """
        for upload in uploads:
            if isinstance(upload, dict):
                self._upload(upload)
            elif upload in uploads and isinstance(uploads[upload], dict):
                self._upload(uploads[upload])
            else:
                raise Exception('invalid upload object')

    def _upload(self, upload):
        """
        Uploads an upload
        :param upload:
        :return:
        """
        self.cdn_handler.upload_file(upload['path'],
                                     '{}/{}'.format(TsV2CatalogHandler.cdn_root_path,
                                                    upload['key']))

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
        lid = TsV2CatalogHandler.sanitize_identifier(language['identifier'], lower=False)

        if rc_type == 'help':
            pid = TsV2CatalogHandler.sanitize_identifier(project['identifier'])

            # tricky some languages may only have supplementary resources and no books
            # so no catalog node will have been built. Therefore we init them here.
            TsV2CatalogHandler._init_catalog_node(catalog, pid, lid)

            for rid in catalog[pid]['_langs'][lid]['_res']:
                res = catalog[pid]['_langs'][lid]['_res'][rid]
                if 'tn' in TsV2CatalogHandler.sanitize_identifier(resource['identifier']):
                    res.update({
                        'notes': '{}/{}/{}/{}/notes.json?date_modified={}'.format(
                            self.cdn_url,
                            TsV2CatalogHandler.cdn_root_path,
                            pid, lid, modified)
                    })
                elif 'tq' in self.sanitize_identifier(resource['identifier']):
                    res.update({
                        'checking_questions': '{}/{}/{}/{}/questions.json?date_modified={}'.format(
                            self.cdn_url,
                            TsV2CatalogHandler.cdn_root_path,
                            pid, lid, modified)
                    })
        elif rc_type == 'dict':
            for pid in catalog:
                # tricky some languages may only have supplementary resources and no books
                # so no catalog node will have been built. Therefore we init them here.
                TsV2CatalogHandler._init_catalog_node(catalog, pid, lid)

                for rid in catalog[pid]['_langs'][lid]['_res']:
                    res = catalog[pid]['_langs'][lid]['_res'][rid]
                    # TRICKY: obs and Bible now use the same words
                    res.update({
                        'terms': '{}/{}/bible/{}/words.json?date_modified={}'.format(
                            self.cdn_url,
                            TsV2CatalogHandler.cdn_root_path,
                            lid, modified)
                    })

    @staticmethod
    def _init_catalog_node(catalog, pid, lid=None, rid=None):
        """
        Initializes a node in the catalog.
        :param catalog: the v2 catalog dictionary
        :param pid: the project id to include in the catalog
        :param lid: the language id to include in the catalog
        :param rid: the resource id to include in the catalog
        :return:
        """
        if pid not in catalog: catalog[pid] = {'_langs': {}}
        if lid is not None:
            if lid not in catalog[pid]['_langs']: catalog[pid]['_langs'][lid] = {'_res': {}, 'language': {}}
        if lid is not None and rid is not None:
            if rid not in catalog[pid]['_langs'][lid]['_res']: catalog[pid]['_langs'][lid]['_res'][rid] = {}

    def _build_catalog_node(self, catalog, language, resource, project, modified, long_modified):
        """
        Creates/updates a node in the catalog
        :param catalog: the v2 catalog dictionary
        :param language: the v3 language catalog object
        :param resource: the v3 resource catalog object
        :param project: the v3 project catalog object
        :param modified:
        :return:
        """
        lid = TsV2CatalogHandler.sanitize_identifier(language['identifier'], lower=False)
        rid = TsV2CatalogHandler.sanitize_identifier(resource['identifier'])
        pid = TsV2CatalogHandler.sanitize_identifier(project['identifier'])

        # TRICKY: v2 api sorted obs with 1
        if pid == 'obs': project['sort'] = 1

        TsV2CatalogHandler._init_catalog_node(catalog, pid, lid, rid)

        # TRICKY: we must process the modified date in the order of resource, language, project to propagate dates correctly

        # resource
        res = catalog[pid]['_langs'][lid]['_res'][rid]
        r_modified = max_modified_date(res, modified)  # TRICKY: dates bubble up from project
        r_long_modified = max_long_modified_date(res, long_modified)  # TRICKY: dates bubble up from project
        comments = ''  # TRICKY: comments are not officially supported in RCs but we use them if available
        if 'comment' in resource: comments = resource['comment']

        # add chunks to non-obs projects
        chunks_url = ''
        if rid != 'obs':
            chunks_url = 'https://api.unfoldingword.org/bible/txt/1/{}/chunks.json'.format(pid)
            # if not self.url_exists(chunks_url) and 'chunks_url' in project:
            # Use the v3 api chunks url if the legacy version cannot be found
            # chunks_url = project['chunks_url']

        source_url = '{}/{}/{}/{}/{}/v{}/source.json?date_modified={}'.format(
            self.cdn_url,
            TsV2CatalogHandler.cdn_root_path,
            pid, lid, rid, resource['version'], r_modified)
        source_text = ''
        source_text_version = ''
        if resource['source']:
            # TRICKY: some resources don't have a source
            source_text = resource['source'][0]['language']
            source_text_version = resource['source'][0]['version']
        # else:
        #     self.report_error('Missing source translation in {} {}'.format(lid, rid))
        res.update({
            'date_modified': r_modified,
            'long_date_modified': r_long_modified,
            'name': resource['title'],
            'notes': '',
            'slug': rid,
            'status': {
                'checking_entity': ', '.join(resource['checking']['checking_entity']),
                'checking_level': resource['checking']['checking_level'],
                'comments': comments,
                'contributors': '; '.join(resource['contributor']),
                'publish_date': resource['issued'],
                'source_text': source_text,  # v2 can only handle one source
                'source_text_version': source_text_version,  # v2 can only handle one source
                'version': resource['version']
            },
            'checking_questions': '',
            'chunks': chunks_url,
            'source': source_url,
            'terms': '',
            'tw_cat': ''
        })

        # TRICKY: use english tw catalog for all languages
        res.update({
            'tw_cat': '{}/{}/{}/{}/tw_cat.json?date_modified={}'.format(
                self.cdn_url,
                TsV2CatalogHandler.cdn_root_path,
                pid, 'en', r_modified)
        })

        # bible projects have usfm
        if pid != 'obs':
            if 'formats' in project:
                for format in project['formats']:
                    if 'text/usfm' == format['format'] or 'text/usfm3' == format['format'] or 'text/usfm2' == format['format']:
                        res.update({
                            'usfm': '{}?date_modified={}'.format(format['url'], r_modified)
                        })
                        break

        # language
        lang = catalog[pid]['_langs'][lid]
        l_modified = max_modified_date(lang['language'], r_modified)  # TRICKY: dates bubble up from resource
        l_long_modified = max_long_modified_date(lang['language'], r_long_modified)  # TRICKY: dates bubble up from resource
        description = ''
        if rid == 'obs': description = resource['description']
        project_meta = list(project['categories'])  # default to category ids
        if 'category_labels' in language:
            project_meta = []
            for cat_id in project['categories']:
                if cat_id in language['category_labels']:
                    project_meta.append(language['category_labels'][cat_id])
                else:
                    project_meta.append(cat_id)

        cat_lang = {
            'language': {
                'date_modified': l_modified,
                'long_date_modified': l_long_modified,
                'direction': language['direction'],
                'name': language['title'],
                'slug': lid
            },
            'project': {
                'desc': description,
                'meta': project_meta,
                'name': project['title']
            },
            'res_catalog': '{}/{}/{}/{}/resources.json?date_modified={}'.format(self.cdn_url,
                                                                                TsV2CatalogHandler.cdn_root_path, pid,
                                                                                lid, l_modified)
        }
        if project['sort']:
            cat_lang['project']['sort'] = '{}'.format(project['sort'])
        lang.update(cat_lang)

        # project
        p_modified = max_modified_date(catalog[pid], l_modified)
        p_long_modified = max_long_modified_date(catalog[pid], l_long_modified)
        catalog[pid].update({
            'date_modified': p_modified,
            'long_date_modified': p_long_modified,
            'lang_catalog': '{}/{}/{}/languages.json?date_modified={}'.format(self.cdn_url,
                                                                              TsV2CatalogHandler.cdn_root_path, pid,
                                                                              p_modified),
            'meta': project['categories'],
            'slug': pid,
            'sort': '{}'.format(project['sort']).zfill(2)
        })
