# Method for handling the registration of conversion modules

from __future__ import print_function

import json

from aws_tools.dynamodb_handler import DynamoDBHandler

def handle(event, context):
    catalog_handler = DynamoDBHandler('catalog-production')
    data = {
        "languages":[
            {
               "slug": "en",
                "name": "English",
                "dir": "ltr",
                "resources": [],
                "check_labels": {
                    "keyword": "Keyword",
                    "metaphor": "Metaphor"
                },
                "category_labels": {
                    "ta": "translationAcademy",
                    "bible-ot": "Bible: OT",
                    "bible-nt": "Bible: NT"
                },
                "versification_labels": {
                    "kjv": "King James Version",
                    "mt": "Masoretic Text (Hebrew Bible)"
                }
            }
        ],
        "catalogs": [
            {
                "slug": "langnames",
                "modified_at": 20151222120130,
                "url": "https://cdn.door43.org/lang/v2/langnames.json"
            },
            {
                "slug": "new-language-questions",
                "modified_at": 20151222120130,
                "url": "http://td.unfoldingword.org/api/questionnaire/"
            }
        ]
    }
    
    for item in catalog_handler.query_items():
        manifest = json.loads(item['manifest'])
        if 'language' in manifest:
            language = manifest['language']
            del manifest['language']
            l = None
            for lang in data['languages']:
                if lang['slug'] == language['slug']:
                    l = lang
            if not l:
                language = manifest['language']
                data['languages'].append(language)
            else:
                language = l
            if 'resources' not in language:
                language['resources'] = []
            language['resources'].append(manifest)

    return data

