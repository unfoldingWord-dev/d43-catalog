# coding=utf-8
import os
import tempfile
import shutil
from unittest import TestCase
from libraries.cli import maptwtousfm3
from libraries.tools.file_utils import read_file
from resource_container import factory

class TestMapTWtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp('-map-tw-usfm')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_index_words(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        index = maptwtousfm3.indexWords(rc)
        self.assertIn('heb/11/4', index)
        self.assertIn('luk/22/30', index)
        self.assertIn('mat/19/28', index)

        self.assertIn('test', index['mat/19/28'])
        self.assertIn('12tribesofisrael', index['mat/19/28'])

    def test_load_strongs(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        strongs = maptwtousfm3.loadStrongs('abomination', rc)
        self.assertEqual(['H887', 'H6292', 'H8251', 'H8262', 'H8441', 'G946', 'G11610'], strongs)

    def test_map_word(self):
        strongs_index = {
            '12tribesofisrael': ['H3478', 'H7626'],
            'abomination': ['H887', 'H6292', 'H8251'],
            'abel': ['H3478', 'H7626']
        }
        words = ['12tribesofisrael', 'abomination', 'abel']
        mapped_word = maptwtousfm3.mapWord('H6292', words, strongs_index)
        self.assertEqual('abomination', mapped_word)

    def test_map_usfm(self):
        usfm = read_file(os.path.join(self.resources_dir, 'usfm/41-MAT.usfm'))
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        words_index = maptwtousfm3.indexWords(rc)
        mappedUSFM = maptwtousfm3.mapUSFM(usfm, rc, words_index)
        expected_usfm = read_file(os.path.join(self.resources_dir, 'mapped_mat.usfm'))
        self.assertEqual(mappedUSFM, expected_usfm)

    def test_map_dir(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        out_dir = os.path.join(self.temp_dir, 'mapped_usfm')
        maptwtousfm3.mapDir(os.path.join(self.resources_dir, 'usfm'), rc, out_dir)