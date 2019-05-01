import os
import yaml
from mock import patch, mock, MagicMock

from unittest import TestCase
from libraries.tools.media_utils import parse_media, _parse_project, _parse_resource, _expand_keys
from libraries.tools.test_utils import assert_object_equals


# This is here to test importing main

class TestMedia(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def test_parse_unquoted_version(self):
        media_yaml = '''
projects:
  -
    identifier: "obs"
    version: {latest}
    media:
      -
       identifier: "pdf"
       version: "1"
       contributor: []
       url: "https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf"'''
        media = yaml.load(media_yaml)
        content_version = '4.1'
        project_chapters = {}
        with self.assertRaises(Exception) as context:
            parse_media(media, content_version, project_chapters)

        self.assertTrue(context.exception.message.startswith('Invalid replacement target'))

    def test_parse_obs_with_chapters(self):
            media_yaml = '''projects:
      -
        identifier: "obs"
        version: "4.1"
        media:
          -
           identifier: "mp3"
           version: "1"
           contributor: []
           quality:
             - "128kbps"
           chapter_url: "https://cdn.door43.org/ylb/obs/v4.1/{quality}/ylb_obs_{chapter}_{quality}.mp3"
           url: "https://cdn.door43.org/ylb/obs/v4.1/{quality}/ylb_obs_{quality}.zip"'''
            media = yaml.load(media_yaml)
            content_version = '4.1'
            project_chapters = {
                'obs': [1]
            }
            resource_formats, project_formats = parse_media(media, content_version, project_chapters)
            expected = {
                'resource_formats': [],
                'project_formats': {
                    'obs': [
                        {
                            'build_rules': ['signing.sign_given_url'],
                            'contributor': [],
                            "chapters": [
                                {
                                    "url": "https://cdn.door43.org/ylb/obs/v4.1/128kbps/ylb_obs_1_128kbps.mp3",
                                    "modified": "",
                                    "length": 0,
                                    "build_rules": [
                                        "signing.sign_given_url"
                                    ],
                                    "signature": "",
                                    "identifier": 1,
                                    "size": 0
                                }
                            ],
                            'format': '',
                            'modified': '',
                            'signature': '',
                            'size': 0,
                            'source_version': '4.1',
                            'quality': '128kbps',
                            'url': 'https://cdn.door43.org/ylb/obs/v4.1/128kbps/ylb_obs_128kbps.zip',
                            'version': '1'
                        }
                    ]
                }
            }
            assert_object_equals(self, expected['resource_formats'], resource_formats)
            assert_object_equals(self, expected['project_formats'], project_formats)

    def test_parse_complete(self):
        media_yaml = '''resource:
    version: "{latest}"
    media:
      -
        identifier: "pdf"
        version: "{latest}"
        contributor: []
        url: "https://cdn.door43.org/en/obs/v{version}/media/{identifier}/obs.pdf"
projects:
  -
    identifier: "obs"
    version: "{latest}"
    media:
      -
       identifier: "pdf"
       version: "1"
       contributor: []
       url: "https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf"'''
        media = yaml.load(media_yaml)
        content_version = '4.1'
        project_chapters = {}
        resource_formats, project_formats = parse_media(media, content_version, project_chapters)
        expected = {
            'resource_formats': [
                {
                    'build_rules': ['signing.sign_given_url'],
                    'contributor': [],
                    'format': '',
                    'modified': '',
                    'signature': '',
                    'size': 0,
                    'source_version': '4.1',
                    'url': 'https://cdn.door43.org/en/obs/v4.1/media/pdf/obs.pdf',
                    'version': '4.1'
                }
            ],
            'project_formats': {
                'obs': [
                    {
                        'build_rules': ['signing.sign_given_url'],
                        'contributor': [],
                        'format': '',
                        'modified': '',
                        'signature': '',
                        'size': 0,
                        'source_version': '4.1',
                        'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf',
                        'version': '1'
                    }
                ]
            }
        }
        assert_object_equals(self, expected['resource_formats'], resource_formats)
        assert_object_equals(self, expected['project_formats'], project_formats)

    def test_parse_resource(self):
        media = {
            'version': '{latest}',
            'media': [
                {
                    'identifier': 'pdf',
                    'version': 1,
                    'contributor': [
                        'First Contributor',
                        'Second Contributor'
                    ],
                    'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf'
                }
            ]
        }
        content_version = '4.1'
        output = _parse_resource(media, content_version)
        expected = [
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf',
                'version': '1'
            }
        ]
        assert_object_equals(self, expected, output)

    def test_parse_project(self):
        media = {
            'identifier': 'obs',
            'version': '{latest}',
            'media': [
                {
                    'identifier': 'pdf',
                    'version': 1,
                    'contributor': [
                        'First Contributor',
                        'Second Contributor'
                    ],
                    'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf'
                }
            ]
        }
        content_version = '4.1'
        chapters = {}
        output = _parse_project(media, content_version, chapters)
        expected = [
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf',
                'version': '1'
            }
        ]
        assert_object_equals(self, expected, output)

    def test_parse_quality(self):
        media = {
            'identifier': 'obs',
            'version': '{latest}',
            'media': [
                {
                    'identifier': 'mp4',
                    'version': 1,
                    'contributor': [
                        'First Contributor',
                        'Second Contributor'
                    ],
                    'quality': [
                        '720p',
                        '360p'
                    ],
                    'url': 'https://cdn.door43.org/obs/txt/1/hmr/{quality}/obs-hmr-v4_1.mp4'
                }
            ]
        }
        content_version = '4.1'
        chapters = {}
        output = _parse_project(media, content_version, chapters)
        expected = [
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'quality': '720p',
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/720p/obs-hmr-v4_1.mp4',
                'version': '1'
            },
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'quality': '360p',
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/360p/obs-hmr-v4_1.mp4',
                'version': '1'
            }
        ]
        assert_object_equals(self, expected, output)

    def test_parse_chapters(self):
        media = {
            'identifier': 'obs',
            'version': '{latest}',
            'media': [
                {
                    'identifier': 'pdf',
                    'version': 1,
                    'contributor': [
                        'First Contributor',
                        'Second Contributor'
                    ],
                    'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf',
                    'chapter_url': 'https://cdn.door43.org/obs/txt/v{version}/hmr/media/{identifier}/obs_{chapter}.pdf'
                }
            ]
        }
        content_version = '4.1'
        chapters = ['01', '02']
        output = _parse_project(media, content_version, chapters)
        expected = [
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/obs-hmr-v4_1.pdf',
                'version': '1',
                'chapters': [
                    {
                        "build_rules": ['signing.sign_given_url'],
                        "identifier": "01",
                        "length": 0,
                        "modified": "",
                        "signature": "",
                        "size": 0,
                        "url": "https://cdn.door43.org/obs/txt/v1/hmr/media/pdf/obs_01.pdf"
                    },
                    {
                        "build_rules": ['signing.sign_given_url'],
                        "identifier": "02",
                        "length": 0,
                        "modified": "",
                        "signature": "",
                        "size": 0,
                        "url": "https://cdn.door43.org/obs/txt/v1/hmr/media/pdf/obs_02.pdf"
                    }
                ]
            }
        ]
        assert_object_equals(self, expected, output)

    def test_parse_chapters_with_quality(self):
        media = {
            'identifier': 'obs',
            'version': '{latest}',
            'media': [
                {
                    'identifier': 'mp4',
                    'version': 1,
                    'contributor': [
                        'First Contributor',
                        'Second Contributor'
                    ],
                    'quality': [
                        '720p',
                        '360p'
                    ],
                    'url': 'https://cdn.door43.org/obs/txt/1/hmr/{quality}/obs-hmr-v4_1.mp4',
                    'chapter_url': 'https://cdn.door43.org/obs/txt/v{version}/hmr/media/{identifier}/{quality}/obs_{chapter}.mp4'
                }
            ]
        }
        content_version = '4.1'
        chapters = ['01', '02']
        output = _parse_project(media, content_version, chapters)
        expected = [
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'quality': '720p',
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/720p/obs-hmr-v4_1.mp4',
                'version': '1',
                'chapters': [
                    {
                        "build_rules": ['signing.sign_given_url'],
                        "identifier": "01",
                        "length": 0,
                        "modified": "",
                        "signature": "",
                        "size": 0,
                        "url": "https://cdn.door43.org/obs/txt/v1/hmr/media/mp4/720p/obs_01.mp4"
                    },
                    {
                        "build_rules": ['signing.sign_given_url'],
                        "identifier": "02",
                        "length": 0,
                        "modified": "",
                        "signature": "",
                        "size": 0,
                        "url": "https://cdn.door43.org/obs/txt/v1/hmr/media/mp4/720p/obs_02.mp4"
                    }
                ]
            },
            {
                'build_rules': ['signing.sign_given_url'],
                'contributor': [
                    'First Contributor',
                    'Second Contributor'
                ],
                'format': '',
                'modified': '',
                'signature': '',
                'size': 0,
                'quality': '360p',
                'source_version': '4.1',
                'url': 'https://cdn.door43.org/obs/txt/1/hmr/360p/obs-hmr-v4_1.mp4',
                'version': '1',
                'chapters': [
                    {
                        "build_rules": ['signing.sign_given_url'],
                        "identifier": "01",
                        "length": 0,
                        "modified": "",
                        "signature": "",
                        "size": 0,
                        "url": "https://cdn.door43.org/obs/txt/v1/hmr/media/mp4/360p/obs_01.mp4"
                    },
                    {
                        "build_rules": ['signing.sign_given_url'],
                        "identifier": "02",
                        "length": 0,
                        "modified": "",
                        "signature": "",
                        "size": 0,
                        "url": "https://cdn.door43.org/obs/txt/v1/hmr/media/mp4/360p/obs_02.mp4"
                    }
                ]
            }
        ]
        assert_object_equals(self, expected, output)

    def test_replace_keys(self):
        url = 'https://example.com/{mykey}/hi/what_{what}/0'
        dict = {
            'mykey':'myvalue',
            'what': 'you'
        }
        new_url = _expand_keys(url, dict)
        self.assertEqual('https://example.com/myvalue/hi/what_you/0', new_url)