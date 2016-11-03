# Method for handling the registration of conversion modules

from __future__ import print_function

import os
import json
import tempfile
import httplib

from urlparse import urlparse
from general_tools.url_utils import get_url


class AcceptanceTest(object):

    def __init__(self, api_url, api_bucket, cdn_url, cdn_bucket, quiet=False):
        self.api_url = api_url
        self.api_bucket = api_bucket
        self.cdn_url = cdn_url
        self.cdn_bucket = cdn_bucket
        self.quiet = quiet
        self.errors = []

    def log_error(self, message):
        if not self.quiet:
            print(message)
        self.errors.append(message)

    def url_exists(self, url):
        p = urlparse(url)
        conn = httplib.HTTPConnection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
        return resp.status == 301 or resp.status == 200

    def test_catalog_structure(self):
        url = '{0}/v3/catalog.json'.format(self.api_url)
        catalog_content = get_url(url, True)
        if not catalog_content:
            self.log_error("{0} does not exist".format(url))
            return False

        try:
            catalog = json.loads(catalog_content)
        except Exception as e:
            self.log_error("{0}".format(e))
            return False

        for key in ['catalogs', 'languages']:
            if key not in catalog:
                self.log_error("{0} doesn't have '{1}'".format(url, key))
        if 'languages' not in catalog:
            return False

        if len(catalog['languages']) < 1:
            self.log_error("There needs to be at least one language in the catalog")
            return False

        if not isinstance(catalog['languages'], list):
            self.log_error("'languages' is not an array")
            return False

        for language in catalog['languages']:
            if not isinstance(language, dict):
                self.log_error("languages: A language container is not an associative array")
                continue

            if 'slug' not in language:
                self.log_error("languages: A language container doesn't have 'slug'")
                continue
            lslug = language['slug']

            for key in ['name', 'dir']:
                if key not in language:
                    self.log_error("{0}: '{0}' does not exist".format(lslug, key))

            if 'resources' in language:
                if not isinstance(language['resources'], list):
                    self.log_error("{0}: 'resources' is not an array".format(lslug))
                else:
                    for resource in language['resources']:
                        if not isinstance(resource, dict):
                            self.log_error("{0}: A resource container is not an associative array")
                            continue

                        if 'slug' not in resource:
                            self.log_error("{0} resources: A resource container exists without a 'slug'".format(lslug))
                            continue
                        rslug = resource['slug']

                        for key in ['name', 'icon', 'status', 'formats']:
                            if key not in resource:
                                self.log_error("{0}: '{1}' does not exist".format(rslug, key))
                        if not isinstance(resource['formats'], list):
                            self.log_error("{0}: 'formats' is not an array".format(rslug))
                        else:
                            for format in resource['formats']:
                                for key in ["mime_type", "modified_at", "size", "url", "sig"]:
                                    if key not in format:
                                        self.log_error("Format container for '{0}' doesn't have '{1}'".format(rslug, key))
                                if 'url' not in format or 'sig' not in format:
                                    continue
                                if not self.url_exists(format['url']):
                                    self.log_error("{0}: {1} does not exist".format(rslug, format['url']))
                                if not format['sig']:
                                    self.log_error("{0}: {1} has not been signed yet".format(rslug, format['url']))
                                elif not self.url_exists(format['sig']):
                                    self.log_error("{0}: {1} does not exist".format(rslug, format['sig']))

    def run(self):
        self.test_catalog_structure()


def handle(event, context):
    api_bucket = retrieve(event, 'api_bucket', "Payload")
    cdn_bucket = retrieve(event, 'cdn_bucket', "Payload")
    api_url = 'https://'+api_bucket
    cdn_url = 'https://'+cdn_bucket

    acceptance = AcceptanceTest(api_url=api_url, api_bucket=api_bucket, cdn_url=cdn_url, cdn_bucket=cdn_bucket)
    acceptance.run()
    print(acceptance.errors)
    return acceptance.errors


def retrieve(dictionary, key, dict_name=None):
    """
    Retrieves a value from a dictionary, raising an error message if the
    specified key is not valid
    :param dict dictionary:
    :param any key:
    :param str|unicode dict_name: name of dictionary, for error message
    :return: value corresponding to key
    """
    if key in dictionary:
        return dictionary[key]
    dict_name = "dictionary" if dict_name is None else dict_name
    raise Exception('{k} not found in {d}'.format(k=repr(key), d=dict_name))


if __name__ == "__main__":
    handle({'api_bucket': 'test-api.door43.org', 'cdn_bucket': 'test-cdn.door43.org'}, None)
