# -*- coding: utf-8 -*-

#
# Class for converting the catalog into a format compatible with the v2 api.
#


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
        # TODO: generate the v2 catalog
        v2_catalog = self.latest_catalog

        return v2_catalog