# coding=utf-8
import os
from unittest import TestCase
from libraries.cli import maptwtousfm3
from libraries.tools.file_utils import read_file

class TestMapTWtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def test_map_file(self):
        usfm = maptwtousfm3.mapWords(os.path.join(self.resources_dir, 'usfm'), os.path.join(self.resources_dir, 'tw_rc'))