# -*- coding: utf-8 -*-

#
# Acceptance Test class
#

from __future__ import print_function

import json
import httplib

from urlparse import urlparse
from general_tools.url_utils import get_url
from aws_tools.ses_handler import SESHandler


class AcceptanceTest(object):
    def __init__(self, catalog_url, to_email=None, from_email=None, quiet=False):
        self.catalog_url = catalog_url
        self.to_email = to_email
        self.from_email = from_email
        self.quiet = quiet
        self.errors = []
        self.ses_handler = SESHandler()

    def log_error(self, message):
        if not self.quiet:
            print(message)
        self.errors.append(message)

    @staticmethod
    def url_exists(url):
        p = urlparse(url)
        conn = httplib.HTTPConnection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
        return resp.status == 301 or resp.status == 200

    def test_catalog_structure(self):
        catalog_content = get_url(self.catalog_url, True)
        if not catalog_content:
            self.log_error("{0} does not exist".format(self.catalog_url))
            return False

        try:
            catalog = json.loads(catalog_content)
        except Exception as e:
            self.log_error("{0}".format(e))
            return False

        for key in ['catalogs', 'languages']:
            if key not in catalog:
                self.log_error("{0} doesn't have '{1}'".format(self.catalog_url, key))
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
        if self.to_email and self.from_email:
            if self.errors:
                response = self.ses_handler.send_email(
                    Source=self.from_email,
                    Destination={
                        'ToAddresses': [
                            self.to_email
                        ]
                    },
                    Message={
                        'Subject': {
                            'Data': 'ERRORS in {0}'.format(self.catalog_url),
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Text': {
                                'Data': 'Errors in {0}: '.format(self.catalog_url) + "\n" + "\n".join(self.errors),
                                'Charset': 'UTF-8'
                            },
                            'Html': {
                                'Data': 'Errors in <a href="{0}">{0}</a>: '.format(
                                    self.catalog_url) + ' <ul><li>' + '</li><li>'.join(self.errors) + '</li></ul>',
                                'Charset': 'UTF-8'
                            }
                        }
                    }
                )
            else:
                response = self.ses_handler.send_email(
                    Source=self.from_email,
                    Destination={
                        'ToAddresses': [
                            self.to_email
                        ]
                    },
                    Message={
                        'Subject': {
                            'Data': 'New {0} was generated'.format(self.catalog_url),
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Text': {
                                'Data': 'New {0} was generated.'.format(self.catalog_url),
                                'Charset': 'UTF-8'
                            },
                            'Html': {
                                'Data': 'New <a href="{0}">{0}</a> was generated.'.format(self.catalog_url),
                                'Charset': 'UTF-8'
                            }
                        }
                    }
                )

