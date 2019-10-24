# coding=utf-8
#
# Class for converting the catalog into a format compatible with the v2 api.
#

from __future__ import unicode_literals
import json
import logging
import math
import os
import shutil
import tempfile
import time
import sys

from hashlib import md5
from d43_aws_tools import S3Handler, DynamoDBHandler
from libraries.tools.date_utils import str_to_unix_time
from libraries.tools.dict_utils import merge_dict
from libraries.tools.file_utils import write_file, read_file
from libraries.tools.legacy_utils import index_obs
from libraries.tools.url_utils import download_file, get_url
from libraries.tools.usfm_utils import strip_word_data, convert_chunk_markers

from libraries.tools.signer import Signer, ENC_PRIV_PEM_PATH
from libraries.lambda_handlers.instance_handler import InstanceHandler

class UwV2CatalogHandler(InstanceHandler):

    cdn_root_path = 'v2/uw'
    api_version = 'uw.2'

    def __init__(self, event, context, logger, **kwargs):
        super(UwV2CatalogHandler, self).__init__(event, context)

        env_vars = self.retrieve(event, 'stage-variables', 'payload')
        self.cdn_bucket = self.retrieve(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = self.retrieve(env_vars, 'cdn_url', 'Environment Vars').rstrip('/')
        self.from_email = self.retrieve(env_vars, 'from_email', 'Environment Vars')
        self.to_email = self.retrieve(env_vars, 'to_email', 'Environment Vars')
        self.logger = logger # type: logging._loggerClass
        self.temp_dir = tempfile.mkdtemp('', 'uw_v2', None)

        if 's3_handler' in kwargs:
            self.cdn_handler = kwargs['s3_handler']
        else:
            self.cdn_handler = S3Handler(self.cdn_bucket) # pragma: no cover

        if 'dynamodb_handler' in kwargs:
            self.db_handler = kwargs['dynamodb_handler']
        else:
            self.db_handler = DynamoDBHandler('{}d43-catalog-status'.format(self.stage_prefix())) # pragma: no cover

        if 'url_handler' in kwargs:
            self.get_url = kwargs['url_handler']
        else:
            self.get_url = get_url # pragma: no cover

        if 'download_handler' in kwargs:
            self.download_file = kwargs['download_handler']
        else:
            self.download_file = download_file # pragma: no cover

        if 'signing_handler' in kwargs:
            self.signer = kwargs['signing_handler']
        else:
            self.signer = Signer(ENC_PRIV_PEM_PATH) # pragma: no cover

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
            return self.__execute()
        except Exception as e:
            self.report_error(e.message)
            raise Exception, Exception(e), sys.exc_info()[2]

    def __execute(self):
        """
        We wrap this in a separate function to more easily handle errors
        :return:
        """
        uploads = []

        result = self._get_status()
        if not result:
            return False
        else:
            (status, source_status) = result

        # check if build is complete
        if status['state'] == 'complete':
            if self.logger:
                self.logger.debug('Catalog already generated')
            return True

        # retrieve the latest catalog
        catalog_content = self.get_url(source_status['catalog_url'], True)
        if not catalog_content:
            if self.logger:
                self.logger.error("{0} does not exist".format(source_status['catalog_url']))
            return False
        try:
            self.latest_catalog = json.loads(catalog_content)
        except Exception as e:
            if self.logger:
                self.logger.error("Failed to load the catalog json: {0}".format(e))
            return False

        catalog = self.convert_v3_to_v2(self.latest_catalog, status)

        catalog_upload = self._prep_json_upload('catalog.json', catalog)
        uploads.append(catalog_upload)
        # TRICKY: also upload to legacy path for backwards compatibility
        uploads.append({
            'key': '/uw/txt/2/catalog.json',
            'path': catalog_upload['path']
        })

        # upload files
        for upload in uploads:
            if not upload['key'].startswith('/'):
                key = '{}/{}'.format(UwV2CatalogHandler.cdn_root_path, upload['key'])
            else:
                key = upload['key'].lstrip('/')
            self.cdn_handler.upload_file(upload['path'], key)

        status['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        status['state'] = 'complete'
        self.db_handler.update_item(
            {'api_version': UwV2CatalogHandler.api_version},
            status)

    def convert_v3_to_v2(self, v3_catalog, status):
        """
        Builds a v2 catalog for the uW api endpoint.
        This uses the v3 catalog as the source
        :param v3_catalog: the v3 catalog
        :param status: the build status retrieved from AWS.
        :return: the complete v2 catalog
        """
        cat_keys = []
        v2_catalog = {
            'obs': {},
            'bible': {}
        }

        title_map = {
            'bible': 'Bible',
            'obs': 'Open Bible Stories'
        }

        last_modified = 0

        for lang in v3_catalog['languages']:
            lid = lang['identifier']
            self.logger.info('Processing {}'.format(lid))
            for res in lang['resources']:
                rid = res['identifier']
                if rid == 'obs':
                    cat_key = 'obs'
                else:
                    cat_key = 'bible'

                mod = str_to_unix_time(res['modified'])

                if int(mod) > last_modified:
                    last_modified = int(mod)

                # TRICKY: we are not processing the resource formats

                toc = []
                for proj in res['projects']:
                    pid = proj['identifier']
                    if 'formats' in proj and proj['formats']:
                        source = None
                        pdf = None
                        media = {
                            'audio': {
                                'src_dict': {}
                            },
                            'video': {
                                'src_dict': {}
                            }
                        }
                        for format in proj['formats']:
                            # skip media formats that do not match the source version
                            if 'source_version' in format and format['source_version'] != res['version']:
                                if self.logger:
                                    self.logger.warning(
                                        '{}_{}_{}: media format "{}" does not match source version "{}" and will be excluded.'.format(
                                            lid, rid, pid, format['url'], res['version']))
                                continue

                            if rid == 'obs' and 'type=book' in format['format']:
                                # TRICKY: obs must be converted to json
                                process_id = '_'.join([lid, rid, pid])
                                obs_key = '{}/{}/{}/{}/v{}/source.json'.format(self.cdn_root_path, pid, lid, rid,
                                                                               res['version'])
                                if process_id not in status['processed']:
                                    obs_json = index_obs(lid, rid, format, self.temp_dir, self.download_file)
                                    upload = self._prep_json_upload(obs_key, obs_json)
                                    self.cdn_handler.upload_file(upload['path'], upload['key'])

                                    # sign obs file.
                                    # TRICKY: we only need to sign obs so we do so now.
                                    sig_file = self.signer.sign_file(upload['path'])
                                    try:
                                        self.signer.verify_signature(upload['path'], sig_file)
                                        self.cdn_handler.upload_file(sig_file, '{}.sig'.format(upload['key']))
                                    except RuntimeError:
                                        if self.logger:
                                            self.logger.warning('Could not verify signature {}'.format(sig_file))

                                    status['processed'].update({process_id: []})
                                    status['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                    self.db_handler.update_item({'api_version': UwV2CatalogHandler.api_version}, status)
                                else:
                                    cat_keys = cat_keys + status['processed'][process_id]

                                source = {
                                    'url': '{}/{}'.format(self.cdn_url, obs_key),
                                    'signature': '{}/{}.sig'.format(self.cdn_url, obs_key)
                                }
                            elif rid != 'obs' and format['format'] == 'text/usfm':
                                # process bible
                                process_id = '_'.join([lid, rid, pid])
                                bible_key = '{0}/{1}/{2}/{3}/v{4}/{1}.usfm'.format(self.cdn_root_path, pid, lid, rid,
                                                                                   res['version'])
                                if process_id not in status['processed']:
                                    usfm = self._process_usfm(format)
                                    upload = self._prep_text_upload(bible_key, usfm)
                                    self.cdn_handler.upload_file(upload['path'], upload['key'])

                                    # sign file
                                    sig_file = self.signer.sign_file(upload['path'])
                                    try:
                                        self.signer.verify_signature(upload['path'], sig_file)
                                        self.cdn_handler.upload_file(sig_file, '{}.sig'.format(upload['key']))
                                    except RuntimeError:
                                        if self.logger:
                                            self.logger.warning('Could not verify signature {}'.format(sig_file))

                                    status['processed'].update({process_id: []})
                                    status['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                    self.db_handler.update_item({'api_version': UwV2CatalogHandler.api_version}, status)
                                else:
                                    cat_keys = cat_keys + status['processed'][process_id]
                                source = {
                                    'url': '{}/{}'.format(self.cdn_url, bible_key),
                                    'signature': '{}/{}.sig'.format(self.cdn_url, bible_key)
                                }
                            elif 'content=audio/mp3' in format['format'] or 'content=video/mp4' in format['format']:
                                # process media
                                quality_value, quality_suffix = self.__parse_media_quality(format['quality'])
                                if 'content=audio/mp3' in format['format']:
                                    media_container = media['audio']
                                    quality_key = 'bitrate'
                                    quality_short_key = 'br'
                                else:
                                    media_container = media['video']
                                    quality_key = 'resolution'
                                    quality_short_key = 'res'

                                # build chapter src
                                src_dict = {}
                                if 'chapters' in format:
                                    for chapter in format['chapters']:
                                        src_dict[chapter['identifier']] = {
                                            quality_short_key: [{
                                                quality_key: int(quality_value),
                                                'mod': int(str_to_unix_time(chapter['modified'])),
                                                'size': chapter['size']
                                            }],
                                            'chap': chapter['identifier'],
                                            'length': int(math.ceil(chapter['length'])),
                                            'src': chapter['url'].replace(format['quality'],
                                                                          '{bitrate}' + quality_suffix),
                                            'src_sig': chapter['signature'].replace(format['quality'],
                                                                                    '{bitrate}' + quality_suffix)
                                        }

                                merge_dict(media_container, {
                                    'contributors': ',\\n'.join(format['contributor']),
                                    'rev': format['version'],
                                    'txt_ver': format['source_version'],
                                    'src_dict': src_dict
                                })
                            elif 'application/pdf' == format['format']:
                                pdf = {
                                    'url': format['url'],
                                    'source_version': format['source_version']
                                }

                        # build catalog
                        if not source:
                            if self.logger:
                                self.logger.debug('No book text found in {}_{}_{}'.format(lid, rid, pid))
                            continue

                        media_keys = media.keys()
                        for key in media_keys:
                            if media[key]['src_dict']:
                                media[key]['src_list'] = [media[key]['src_dict'][k] for k in media[key]['src_dict']]
                                del media[key]['src_dict']
                            else:
                                del media[key]
                        toc_item = {
                            'desc': '',
                            'media': media,
                            'mod': mod,
                            'slug': proj['identifier'],
                            'src': source['url'],
                            'src_sig': source['signature'],
                            'title': proj['title'],
                        }
                        if rid == 'obs':
                            del toc_item['slug']
                        if pdf:
                            toc_item['pdf'] = pdf['url']

                        if not media:
                            del toc_item['media']
                        toc.append(toc_item)

                if not toc:
                    continue

                # TRICKY: not all manifests have a source text
                if 'source' in res and len(res['source']):
                    source = res['source'][0]
                else:
                    source = {
                        'language': '',
                        'version': ''
                    }

                comment = ''
                if 'comment' in res:
                    comment = res['comment']

                # TRICKY: maintain legacy slug formatting for backwards compatibility
                legacy_slug = '{}-{}'.format(rid, lid)
                res_v2_id = rid
                if legacy_slug in self.legacy_slugs or rid == 'obs':
                    res_v2_id = legacy_slug

                res_v2 = {
                    'slug': res_v2_id,
                    'name': res['title'],
                    'mod': mod,
                    'status': {
                        'checking_entity': '; '.join(res['checking']['checking_entity']),
                        'checking_level': res['checking']['checking_level'],
                        'comments': comment,
                        'contributors': '; '.join(res['contributor']),
                        'publish_date': res['issued'],
                        'source_text': source['language'],
                        'source_text_version': source['version'],
                        'version': res['version']
                    },
                    'toc': toc
                }

                if not lid in v2_catalog[cat_key]:
                    v2_catalog[cat_key][lid] = {
                        'lc': lid,
                        'mod': mod,
                        'vers': []
                    }
                v2_catalog[cat_key][lid]['vers'].append(res_v2)

        # condense catalog
        catalog = {
            'cat': [],
            'mod': last_modified
        }
        for cat_slug in v2_catalog:
            langs = []
            for lid in v2_catalog[cat_slug]:
                langs.append(v2_catalog[cat_slug][lid])

            catalog['cat'].append({
                'slug': cat_slug,
                'title': title_map[cat_slug],
                'langs': langs
            })
        return catalog

    def _process_usfm(self, format):
        url = format['url']
        usfm_file = os.path.join(self.temp_dir, md5(url).hexdigest())
        self.download_file(url, usfm_file)
        usfm = read_file(usfm_file)
        return convert_chunk_markers(strip_word_data(usfm))


    def _get_status(self):
        """
        Retrieves the catalog status from AWS.

        :return: A tuple containing the status object of the target and source catalogs, or False if the source is not ready
        """
        status_results = self.db_handler.query_items({
            'api_version': {
                'condition': 'is_in',
                'value': ['3', UwV2CatalogHandler.api_version]
            }
        })
        source_status = None
        status = None
        for s in status_results:
            if s['api_version'] == '3':
                source_status = s
            elif s['api_version'] == UwV2CatalogHandler.api_version:
                status = s
        if not source_status:
            if self.logger:
                self.logger.debug('Source catalog status not found')
            return False
        if source_status['state'] != 'complete':
            if self.logger:
                self.logger.debug('Source catalog is not ready for use')
            return False
        if not status or status['source_timestamp'] != source_status['timestamp']:
            # begin or restart process
            status = {
                'api_version': UwV2CatalogHandler.api_version,
                'catalog_url': '{}/uw/txt/2/catalog.json'.format(self.cdn_url),
                'source_api': source_status['api_version'],
                'source_timestamp': source_status['timestamp'],
                'state': 'in-progress',
                'processed': {}
            }

        return (status, source_status)

    def _prep_json_upload(self, key, data):
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

    def _prep_text_upload(self, key, data):
        """
        Prepares some data for upload to s3
        :param key:
        :param data:
        :return:
        """
        temp_file = os.path.join(self.temp_dir, key)
        write_file(temp_file, data)
        return {
            'key': key,
            'path': temp_file
        }

    def __parse_media_quality(self, quality):
        """
        Returns the value and suffix from the quality
        :param quality:
        :return:
        """
        abc = 'abcdefghijklmnopqrstufwxyz'
        value = quality.rstrip('{}{}'.format(abc, abc.upper()))
        suffix = quality[len(value):]
        return value, suffix


    # 'legacy_slugs' contains a list of legacy slugs for resources 'vers'. Legacy slugs are formatted as `res-lang`
    legacy_slugs = [
        "ulb-ceb",
        "udb-ceb",
        "ulb-ee",
        "ulb-en",
        "udb-en",
        "ulb-hna",
        "ulb-ilo",
        "ulb-kbp",
        "ulb-kpo",
        "ulb-las",
        "ulb-lpx"
    ]
