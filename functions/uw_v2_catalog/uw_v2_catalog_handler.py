# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the v2 api.
#

import time
from datetime import datetime

def datestring_to_timestamp(datestring):
    return str(int(time.mktime(datetime.strptime(datestring[:10], "%Y-%m-%d").timetuple())))

class UwV2CatalogHandler:

    def __init__(self, catalog):
        """
        Initializes the converter with the catalog from which to generate the v2 catalog
        :param catalog: the latest catalog
        """
        self.latest_catalog = catalog

    def convert_catalog(self):
        """
        Generates the v2 catalog
        :return: the v2 form of the catalog
        """
        v2_catalog = {
            'obs': {},
            'bible': {}
        }

        res_map = {
            'ulb': 'bible',
            'udb': 'bible',
            'obs': 'obs'
        }

        for lang in self.latest_catalog['languages']:
            lang_slug = lang['identifier']
            for res in lang['resources']:
                res_type = res['identifier']
                print(res_type)
                key = res_map[res_type] if res_type in res_map else None

                if not key:
                    continue

                mod = datestring_to_timestamp(res['modified'])

                # TODO: figure out how to handle "formats" and the chunks

                toc = []
                for proj in res['projects']:
                    toc.append({
                        'slug': proj['identifier'],
                        'title': proj['title'],
                        'mod': mod
                    })

                source = res['source'][0]
                res_v2 = {
                    'slug': res_type, # TODO: check if should have lang_slug
                    'name': res['title'],
                    'mod': mod,
                    'status': {
                        'contributors': ', '.join(res['contributor']),
                        'version': res['version'],
                        'source_text_version': source['version'],
                        'source_text': source['identifier'] + '-' + source['language']
                    },
                    'toc': toc
                }

                if not lang_slug in v2_catalog[key]:
                    v2_catalog[key][lang_slug] = []
                v2_catalog[key][lang_slug].append(res_v2)

        return v2_catalog