# coding=utf-8
import os
import shutil
import tempfile
from unittest import TestCase
from libraries.tools.legacy_utils import index_obs
from libraries.tools.mocks import MockAPI


class TestIndexOBS(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='test_index_obs_')

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_index_inconsistent_image_titles(self):
        mockApi = MockAPI(self.resources_dir, 'https://example.com')
        format = {
            'format': 'type=book',
            'url': 'https://example.com/en_obs.zip'
        }
        response = index_obs('en', 'obs', format, self.temp_dir, mockApi.download_file)
        chapters = response['chapters']
        self.assertEqual(2, len(chapters))

        self.assertEqual('01', chapters[0]['number'])
        self.assertEqual(16, len(chapters[0]['frames']))
        frames = chapters[0]['frames']
        self.assertEqual('01-01', frames[0]['id'])
        self.assertEqual('01-02', frames[1]['id'])

        self.assertEqual('02', chapters[1]['number'])
        self.assertEqual(12, len(chapters[1]['frames']))

