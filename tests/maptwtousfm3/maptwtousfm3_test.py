# coding=utf-8
import os
from unittest import TestCase
from libraries.cli import maptwtousfm3
from libraries.tools.file_utils import read_file
from resource_container import factory

class TestMapTWtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def test_index_tw(self):
        rc = factory.load(os.path.join(self.resources_dir, 'small_tw_rc'))
        index = maptwtousfm3.indexLocationWords(rc)
        self.assertIn('heb/11/4', index)
        self.assertIn('luk/22/30', index)
        self.assertIn('mat/19/28', index)

        self.assertIn('test', index['mat/19/28'])
        self.assertIn('12tribesofisrael', index['mat/19/28'])

    def test_get_strongs(self):
        rc = factory.load(os.path.join(self.resources_dir, 'small_tw_rc'))
        strongs = maptwtousfm3.getStrongNumbers('abomination', rc)
        self.assertEqual(['H887', 'H6292', 'H8251', 'H8262', 'H8263', 'H8441', 'G946'], strongs)

    def test_map_word(self):
        rc = factory.load(os.path.join(self.resources_dir, 'small_tw_rc'))
        maptwtousfm3.mapWord('H887', rc, )

    def test_map_file(self):
        usfm = maptwtousfm3.mapWords(os.path.join(self.resources_dir, 'usfm'), os.path.join(self.resources_dir, 'tw_rc'))
