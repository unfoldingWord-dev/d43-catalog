# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the tS v2 api.
#

import json
from datetime import datetime
import dateutil.parser

class TsV2CatalogHandler:

    def __init__(self, catalog, ):
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
        v2_catalog = []
        for language in self.latest_catalog['languages']:
            for resource in language['resources']:
                modified = None
                rc_type = None
                if 'formats' in resource:
                    for format in resource['formats']:
                        modified = self._convert_date(format['modified'])
                        if 'type=bundle' in format['format']:
                            rc_type = 'bundle'
                            # TODO: retrieve book data from resource zip
                            break

                for project in resource['projects']:
                    if 'formats' in project:
                        for format in project['formats']:
                            modified = self._convert_date(format['modified'])
                            if 'type=book' in format['format']:
                                rc_type = 'book'
                                # TODO: retrieve book data
                                break

                    if modified is None:
                        raise Exception('Could not find date_modified for {}_{}_{}'.format(language['identifier'], resource['identifier'], project['identifier']))

                    if rc_type == 'book' or rc_type == 'bundle':
                        if project['identifier'] == 'obs': project['sort'] = 1
                        v2_catalog.append({
                            'date_modified': modified,
                            'lang_catalog': 'https://api.unfoldingword.org/ts/txt/2/{}/languages.json?date_modified={}'.format(
                                project['identifier'], modified),
                            'meta': project['categories'],
                            'slug': project['identifier'],
                            'sort': '{}'.format(project['sort']).zfill(2)
                        })

        return v2_catalog

    def _convert_date(self, date_str):
        """
        Converts a date from the UTC format (used in api v3) to the form in api v2.
        :param date_str: 
        :return: 
        """
        date_obj = dateutil.parser.parse(date_str)
        return date_obj.strftime('%Y%m%d')
