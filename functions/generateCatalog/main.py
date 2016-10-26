# Method for handling the registration of conversion modules

from __future__ import print_function

import os
import json
import tempfile

from general_tools.file_utils import write_file
from aws_tools.dynamodb_handler import DynamoDBHandler
from aws_tools.s3_handler import S3Handler

VERSION = 3

def handle(event, context):
    print(context.invoked_function_arn)

    if '581647696645' in context.invoked_function_arn:
        api_bucket = 'test-api.door43.org'
    else:
        api_bucket = 'api.door43.org'

    catalog_handler = DynamoDBHandler('catalog-production')
    data = {
        "languages": []
    }
    
    for item in catalog_handler.query_items():
        repo_name = item['repo_name']
        print(repo_name)
        contents = json.loads(item['contents'])
        if repo_name == "catalogs":
            data['catalogs'] = contents
        else:
            if 'language' in contents:
                language = contents['language']
                del contents['language']
                l = None
                for lang in data['languages']:
                    if lang['slug'] == language['slug']:
                        l = lang
                if not l:
                    data['languages'].append(language)
                else:
                    language = l
                if repo_name.startswith('localization_'):
                    language['localization'] = contents
                else:
                    if 'resources' not in language:
                        language['resources'] = []
                    language['resources'].append(contents)

    catalog_path = os.path.join(tempfile.gettempdir(), 'catalog.json')
    write_file(catalog_path, data)
    s3handler = S3Handler(api_bucket)
    s3handler.upload_file(catalog_path, 'v{0}/catalog.json'.format(VERSION), cache_time=0)

    return data

