from libraries.lambda_handlers.handler import Handler

import json
from urlparse import urlparse

class AcceptanceHandler(Handler):

    def __init__(self, event, context, catalog_url, URLHandler, HTTPConnection, SESHandler, **kwargs):
        super(AcceptanceHandler, self).__init__(event, context)

        self.catalog_url = catalog_url
        if 'to_email' in kwargs:
            self.to_email = kwargs['to_email']
        else:
            self.to_email = None
        if 'from_email' in kwargs:
            self.from_email = kwargs['from_email']
        else:
            self.from_email = None
        if 'quiet' in kwargs:
            self.quiet = kwargs['quiet']
        else:
            self.quiet = None
        self.errors = []
        self.ses_handler = SESHandler()
        self.http_connection = HTTPConnection
        self.url_handler = URLHandler()

    def log_error(self, message):
        if not self.quiet:
            print(message)
        self.errors.append(message)

    def url_exists(self, url):
        p = urlparse(url)
        conn = self.http_connection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
        return resp.status == 301 or resp.status == 200

    def test_catalog_structure(self):
        catalog_content = self.url_handler.get_url(self.catalog_url, True)
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
                self.log_error("{} doesn't have '{}'".format(self.catalog_url, key))
        if 'languages' not in catalog:
            return False

        self._test_languages(catalog['languages'])


    def _test_languages(self, languages):
        if not isinstance(languages, list):
            self.log_error("'languages' is not an array")
            return False

        if len(languages) < 1:
            self.log_error("There needs to be at least one language in the catalog")
            return False

        for language in languages:
            if not isinstance(language, dict):
                self.log_error("languages: Found a language container that is not an associative array")
                continue

            if 'identifier' not in language:
                self.log_error("languages: Found a language container that doesn't have 'identifier'")
                continue
            lslug = language['identifier']

            for key in ['title', 'direction']:
                if key not in language:
                    self.log_error("{}: '{}' does not exist".format(lslug, key))

            if 'resources' in language:
                self._test_resources(lslug, language['resources'])

    def _test_resources(self, lslug, resources):
        if not isinstance(resources, list):
            self.log_error("{}: 'resources' is not an array".format(lslug))
        else:
            for resource in resources:
                if not isinstance(resource, dict):
                    self.log_error("{}: Found a resource container that is not an associative array".format(lslug))
                    continue

                if 'identifier' not in resource:
                    self.log_error("{} resources: A resource container exists without an 'identifier'".format(lslug))
                    continue
                rslug = resource['identifier']

                for key in ['title', 'source', 'rights', 'creator', 'contributor', 'relation', 'publisher',
                            'issued', 'modified', 'version', 'checking', 'projects']:
                    if key not in resource:
                        self.log_error("{}_{}: resource is missing '{}'".format(lslug, rslug, key))

                if 'projects' in resource:
                    self._test_projects(lslug, rslug, resource['projects'], resource)

                if 'formats' in resource:
                    self._test_formats(resource['formats'], lslug, rslug)

    def _test_projects(self, lslug, rslug, projects, resource):
        if not isinstance(projects, list):
            self.log_error("{}_{}: 'projects' is not an array".format(lslug, rslug))
            return
        elif len(projects) > 1 and 'formats' not in resource:
            self.log_error("{}_{}: 'formats' does not exist in multi-project resource".format(lslug, rslug))
        elif len(projects) == 1 and 'formats' in resource:
            self.log_error("{}_{}: 'formats' found in single-project resource".format(lslug, rslug))
        for project in projects:
            if not isinstance(project, dict):
                self.log_error("{}_{}: project is not a dictionary".format(lslug, rslug))
                continue
            for key in ['categories', 'identifier', 'sort', 'title', 'versification']:
                if not key in project:
                    self.log_error("{}_{}: project missing '{}'".format(lslug, rslug, key))
            if 'format' in project:
                self._test_formats(project['formats'], lslug, rslug, project['identifier'])

    def _test_formats(self, formats, lslug, rslug, pslug=None):
        if not isinstance(formats, list):
            self.log_error("{}_{}: 'formats' is not an array".format(lslug, rslug))
        else:
            for format in formats:
                for key in ["format", "modified", "size", "url", "signature"]:
                    if key not in format:
                        self.log_error("Format container for '{}_{}' doesn't have '{}'".format(lslug, rslug, key))
                if 'url' not in format or 'signature' not in format:
                    continue
                if not self.url_exists(format['url']):
                    self.log_error("{}_{}: {} does not exist".format(lslug, rslug, format['url']))
                if not format['signature']:
                    self.log_error("{}_{}: {} has not been signed yet".format(lslug, rslug, format['url']))
                elif not self.url_exists(format['signature']):
                    self.log_error("{}_{}: {} does not exist".format(lslug, rslug, format['signature']))

                if not pslug and 'chapters' in format:
                    self.log_error('{}_{}: chapters can only be in project formats'.format(lslug, rslug))

                # test media requirements
                if pslug:
                    for key in ['content=video', 'content=audio']:
                        if key in format['format'] and 'quality' not in format:
                            self.log_error("{}_{}: Missing 'quality' key in media format".format(lslug, rslug))
                    if 'chapters' in format:
                        self._test_chapters(lslug, rslug, pslug, format['chapters'])

    def _test_chapters(self, lslug, rslug, pslug, chapters):
        for chapter in chapters:
            for key in ['format', 'identifier', 'modified', 'signature', 'size', 'url']:
                if key not in chapter:
                    self.log_error('{}_{}_{}: chapter format is missing "{}"'.format(lslug, rslug, pslug, key))
            if 'format' in chapter:
                for key in ['audio', 'video']:
                    if key in chapter['format'] and 'length' not in chapter:
                        self.log_error('{}_{}_{}: chapter media format is missing "length"'.format(lslug, rslug, pslug))
            if 'url' in chapter and not self.url_exists(chapter['url']):
                self.log_error("{}_{}_{}: '{}' does not exist".format(lslug, rslug, pslug, chapter['url']))
            if 'signature' in chapter and not self.url_exists(chapter['signature']):
                self.log_error("{}_{}_{}: '{}' does not exist".format(lslug, rslug, pslug, chapter['signature']))

    def _run(self, **kwargs):
        self.test_catalog_structure()
        if self.to_email and self.from_email:
            try:
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
            except Exception as e:
                print("ALERT! FAILED TO SEND EMAIL: {}".format(e))

        return self.errors