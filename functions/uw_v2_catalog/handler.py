# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the v2 api.
#

import time
import json
import shutil
import tempfile
import os
from tools.file_utils import write_file
from d43_aws_tools import S3Handler, DynamoDBHandler
from tools.dict_utils import read_dict, merge_dict
from tools.url_utils import download_file, get_url
from tools.signer import Signer, ENC_PRIV_PEM_PATH
from tools.date_utils import str_to_unix_time
from tools.legacy_utils import index_obs
import math
import logging


class UwV2CatalogHandler:

    cdn_root_path = 'v2/uw'
    api_version = 'uw.2'

    def __init__(self, event, logger, s3_handler=None, dynamodb_handler=None, url_handler=None, download_handler=None, signing_handler=None):
        """
        Initializes the converter with the catalog from which to generate the v2 catalog
        :param event:
        :param s3_handler: This is passed in so it can be mocked for unit testing
        :param dynamodb_handler: This is passed in so it can be mocked for unit testing
        :param url_handler: This is passed in so it can be mocked for unit testing
        :param download_handler: This is passed in so it can be mocked for unit testing
        """
        env_vars = read_dict(event, 'stage-variables', 'payload')
        self.cdn_bucket = read_dict(env_vars, 'cdn_bucket', 'Environment Vars')
        self.cdn_url = read_dict(env_vars, 'cdn_url', 'Environment Vars')
        self.cdn_url = self.cdn_url.rstrip('/')
        self.logger = logger # type: logging._loggerClass
        if not s3_handler:
            self.cdn_handler = S3Handler(self.cdn_bucket) # pragma: no cover
        else:
            self.cdn_handler = s3_handler
        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler('d43-catalog-status') # pragma: no cover
        else:
            self.db_handler = dynamodb_handler
        if not url_handler:
            self.get_url = get_url # pragma: no cover
        else:
            self.get_url = url_handler
        if not download_handler:
            self.download_file = download_file # pragma: no cover
        else:
            self.download_file = download_handler

        self.temp_dir = tempfile.mkdtemp('', 'uwv2', None)
        if not signing_handler:
            self.signer = Signer(ENC_PRIV_PEM_PATH) # pragma: no cover
        else:
            self.signer = signing_handler

    def __del__(self):
        try:
            shutil.rmtree(self.temp_dir)
        finally:
            pass

    def run(self):
        """
        Generates the v2 catalog
        :return:
        """
        cat_keys = []
        uploads = []
        v2_catalog = {
            'obs': {},
            'bible': {}
        }

        title_map = {
            'bible': 'Bible',
            'obs': 'Open Bible Stories'
        }

        last_modified = 0

        result = self._get_status()
        if not result:
            return False
        else:
            (status, source_status) = result

        # check if build is complete
        if status['state'] == 'complete':
            if self.logger:
                self.logger.info('Catalog already generated')
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

        # walk v3 catalog
        for lang in self.latest_catalog['languages']:
            lid = lang['identifier']
            for res in lang['resources']:
                rid = res['identifier']
                if rid == 'obs':
                    cat_key = 'obs'
                else:
                    cat_key = 'bible'

                mod = str_to_unix_time(res['modified'])

                if int(mod) > last_modified:
                    last_modified = int(mod)

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
                                obs_key = '{}/{}/{}/{}/v{}/source.json'.format(self.cdn_root_path, pid, lid, rid, res['version'])
                                if process_id not in status['processed']:
                                    obs_json = index_obs(lid, rid, format, self.temp_dir, self.download_file)
                                    upload = self._prep_data_upload(obs_key, obs_json)
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
                                source = format
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
                                            'src': chapter['url'].replace(format['quality'], '{bitrate}' + quality_suffix),
                                            'src_sig': chapter['signature'].replace(format['quality'], '{bitrate}' + quality_suffix)
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
                                self.logger.info('No book text found in {}_{}_{}'.format(lid, rid, pid))
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
                        if pdf:
                            toc_item['pdf'] = pdf['url']

                        if not media:
                            del toc_item['media']
                        toc.append(toc_item)

                if not toc:
                    continue

                source = res['source'][0]
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

        catalog_upload = self._prep_data_upload('catalog.json', catalog)
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
                self.logger.info('Source catalog status not found')
            return False
        if source_status['state'] != 'complete':
            if self.logger:
                self.logger.info('Source catalog is not ready for use')
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