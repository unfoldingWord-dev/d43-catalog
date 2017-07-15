# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the v2 api.
#

import time
from datetime import datetime
import pytz
import json
import shutil
import tempfile
import os
from tools.file_utils import write_file
from d43_aws_tools import S3Handler, DynamoDBHandler
from tools.dict_utils import read_dict
from tools.url_utils import download_file, get_url
from tools.legacy_utils import index_obs

def datestring_to_timestamp(datestring):
    # TRICKY: force all datestamps to PST to normalize unit tests across servers.
    tz = pytz.timezone("US/Pacific")
    return str(int(time.mktime(tz.localize(datetime.strptime(datestring[:10], "%Y-%m-%d")).timetuple())))

class UwV2CatalogHandler:

    cdn_root_path = 'v2/uw'
    api_version = 'uw.2'

    def __init__(self, event, s3_handler=None, dynamodb_handler=None, url_handler=None, download_handler=None):
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
        self.cdn_url = read_dict(env_vars, 'cdn_url', 'Environment Vars').rstrip('/')
        if not s3_handler:
            self.cdn_handler = S3Handler(self.cdn_bucket)
        else:
            self.cdn_handler = s3_handler
        if not dynamodb_handler:
            self.db_handler = DynamoDBHandler('d43-catalog-status')
        else:
            self.db_handler = dynamodb_handler
        if not url_handler:
            self.get_url = get_url
        else:
            self.get_url = url_handler
        if not download_handler:
            self.download_file = download_file
        else:
            self.download_file = download_handler

        self.temp_dir = tempfile.mkdtemp('', 'uwv2', None)

    def __del__(self):
        try:
            shutil.rmtree(self.temp_dir)
        finally:
            pass

    def run(self):
        """
        Generates the v2 catalog
        :return: the v2 form of the catalog
        """
        cat_keys = []
        uploads = []
        v2_catalog = {
            'obs': {},
            'bible': {}
        }

        res_map = {
            'ulb': 'bible',
            'udb': 'bible',
            'obs': 'obs'
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
            print('Catalog already generated')
            return True

        # retrieve the latest catalog
        catalog_content = self.get_url(source_status['catalog_url'], True)
        if not catalog_content:
            print("ERROR: {0} does not exist".format(source_status['catalog_url']))
            return False
        try:
            self.latest_catalog = json.loads(catalog_content)
        except Exception as e:
            print("ERROR: Failed to load the catalog json: {0}".format(e))
            return False

        # walk v3 catalog
        for lang in self.latest_catalog['languages']:
            lid = lang['identifier']
            for res in lang['resources']:
                rid = res['identifier']
                key = res_map[rid] if rid in res_map else None

                if not key:
                    continue

                mod = datestring_to_timestamp(res['modified'])

                if int(mod) > last_modified:
                    last_modified = int(mod)

                toc = []
                for proj in res['projects']:
                    pid = proj['identifier']
                    if 'formats' in proj and proj['formats']:
                        format = proj['formats'][0]
                        # TRICKY: obs must be converted to json
                        if rid == 'obs':
                            process_id = '_'.join([lid, rid, pid])
                            if process_id not in status['processed']:
                                obs_json = index_obs(lid, rid, format, self.temp_dir, self.download_file)
                                upload = self._prep_data_upload('{}/{}/source.json'.format(rid, lid), obs_json)
                                self.cdn_handler.upload_file(upload['path'],
                                                             '{}/{}'.format(UwV2CatalogHandler.cdn_root_path,
                                                                            upload['key']))

                                status['processed'].update({process_id: []})
                                status['timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                self.db_handler.update_item({'api_version': UwV2CatalogHandler.api_version}, status)
                            else:
                                cat_keys = cat_keys + status['processed'][process_id]

                            format = {
                                'url': '{}/en/udb/v4/obs.json'.format(self.cdn_url),
                                'signature': '{}/en/udb/v4/obs.json.sig'.format(self.cdn_url)
                            }
                        # generate media

                        # build catalog
                        toc.append({
                            'desc': '',
                            'media': {
                                'audio': {},
                                'video': {}
                            },
                            'mod': mod,
                            'slug': proj['identifier'],
                            'src': format['url'],
                            'src_sig': format['signature'],
                            'title': proj['title'],
                        })
                    else:
                        print('WARNING: skipping lang:{} proj:{} because no formats were found'.format(lid, proj['identifier']))

                source = res['source'][0]
                comment = ''
                if 'comment' in res:
                    comment = res['comment']
                res_v2 = {
                    'slug': rid,
                    'name': res['title'],
                    'mod': mod,
                    'status': {
                        'checking_entity': '; '.join(res['checking']['checking_entity']),
                        'checking_level': res['checking']['checking_level'],
                        'comments': comment,
                        'contributors': '; '.join(res['contributor']),
                        'publish_date': res['issued'],
                        'source_text': source['identifier'] + '-' + source['language'],
                        'source_text_version': source['version'],
                        'version': res['version']
                    },
                    'toc': toc
                }

                if not lid in v2_catalog[key]:
                    v2_catalog[key][lid] = {
                        'lc': lid,
                        'mod': mod,
                        'vers': []
                    }
                v2_catalog[key][lid]['vers'].append(res_v2)

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

        uploads.append(self._prep_data_upload('catalog.json', catalog))

        # upload files
        for upload in uploads:
            self.cdn_handler.upload_file(upload['path'], '{}/{}'.format(UwV2CatalogHandler.cdn_root_path, upload['key']))

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
            print('Source catalog status not found')
            return False
        if source_status['state'] != 'complete':
            print('Source catalog is not ready for use')
            return False
        if not status or status['source_timestamp'] != source_status['timestamp']:
            # begin or restart process
            status = {
                'api_version': UwV2CatalogHandler.api_version,
                'catalog_url': '{}/{}/catalog.json'.format(self.cdn_url, UwV2CatalogHandler.cdn_root_path),
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