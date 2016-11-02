# Method for handling the registration of conversion modules

from __future__ import print_function

import os
import json
import tempfile

from general_tools.file_utils import write_file
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler

VERSION = 3


# gets the existing language container or creates a new one
def get_language(data, language):
    found_lang = None
    for lang in data['languages']:
        if lang['slug'] == language['slug']:
            found_lang = lang
    if not found_lang:
        data['languages'].append(language)
    else:
        language = found_lang
    return language


def handle(event, context):
    print(context.invoked_function_arn)

    if '581647696645' in context.invoked_function_arn:
        api_bucket = 'test-api.door43.org'
    else:
        api_bucket = 'api.door43.org'

    catalog_handler = DynamoDBHandler('d43-catalog-in-progress')

    catalog = {
        "languages": []
    }

    items = catalog_handler.query_items()
    latest = {}

    for item in items:
        if item['repo_name'] in latest:
            if item['timestamp'] > latest[item['repo_name']]['timestamp']:
                latest[item['repo_name']] = item
        else:
            latest[item['repo_name']] = item

    for repo_name in sorted(latest):
        print(repo_name)
        item = latest[repo_name]
        data = json.loads(item['data'])
        if repo_name == "catalogs":
            catalog['catalogs'] = data
        elif repo_name == 'localization':
            for lang in data:
                localization = data[lang]
                language = localization['language']
                del localization['language']
                language = get_language(catalog, language)  # gets the existing language container or creates a new one
                language.update(localization)
        else:
            if 'language' in data:
                language = data['language']
                del data['language']
                language = get_language(catalog, language)  # gets the existing language container or creates a new one
                if 'resources' not in language:
                    language['resources'] = []
                language['resources'].append(data)

    catalog_path = os.path.join(tempfile.gettempdir(), 'catalog.json')
    write_file(catalog_path, catalog)
    s3handler = S3Handler(api_bucket)
    s3handler.upload_file(catalog_path, 'v{0}/catalog.json'.format(VERSION), cache_time=0)

    return catalog

