# coding=utf-8
import os
import tempfile
import shutil
from unittest import TestCase
from libraries.cli import maptwtousfm3
from libraries.tools.file_utils import read_file
from libraries.tools.test_utils import assert_object_equals_file
from resource_container import factory

class TestMapTWtoUSFM3(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp('-map-tw-usfm')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_index_words(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        index = maptwtousfm3.indexWordsLocation(rc)
        self.assertIn('heb/11/4', index['occurrences'])
        self.assertIn('luk/22/30', index['occurrences'])
        self.assertIn('mat/19/28', index['occurrences'])

        self.assertIn('test', index['occurrences']['mat/19/28'])
        self.assertIn('12tribesofisrael', index['occurrences']['mat/19/28'])

    def test_load_strongs(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        strongs = maptwtousfm3.findStrongs('abomination', rc)
        self.assertEqual(['H887', 'H6292', 'H8251', 'H8262', 'H8441', 'G946', 'G11610'], strongs)

    def test_map_word(self):
        strongs_index = {
            '12tribesofisrael': ['H3478', 'H7626'],
            'abomination': ['H887', 'H6292', 'H8251'],
            'abel': ['H3478', 'H7626']
        }
        words = ['12tribesofisrael', 'abomination', 'abel']
        mapped_word = maptwtousfm3.getStrongWords('H6292', words, strongs_index)
        self.assertTrue(len(mapped_word) == 1)
        self.assertEqual('abomination', mapped_word[0])

    def test_map_usfm_by_occurrence(self):
        usfm = read_file(os.path.join(self.resources_dir, 'usfm/41-MAT.usfm'))
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        words_index = maptwtousfm3.indexWordsLocation(rc)
        mappedUSFM = maptwtousfm3.mapUSFMByOccurrence(usfm, rc, words_index['occurrences'])
        expected_usfm = read_file(os.path.join(self.resources_dir, 'mapped_mat.usfm'))
        self.assertEqual(mappedUSFM, expected_usfm)

    def test_titus_multiple_word_match(self):
        """
        Ensures we are correctly finding multiple word matches in Titus.
        :return:
        """
        usfm = read_file(os.path.join(self.resources_dir, 'usfm/57-TIT.usfm'))
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        words_index = maptwtousfm3.indexWordsLocation(rc)
        mappedUSFM = maptwtousfm3.mapUSFMByOccurrence(usfm, rc, words_index['occurrences'])
        expected_usfm = read_file(os.path.join(self.resources_dir, 'mapped_tit.usfm'))
        self.assertEqual(mappedUSFM, expected_usfm)

    def test_index_words_by_strongs(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        strongs_index = maptwtousfm3.indexWordByStrongs(rc)
        expected = {
          "G11610": ["abomination"],
          "G60000": ["abel"],
          "G94600": ["abomination","test"],
          "H62920": ["abomination","test"],
          "H34780": ["12tribesofisrael"],
          "H81470": ["12tribesofisrael"],
          "G35880": ["abel"],
          "H84410": ["abomination","test"],
          "G09760": ["test"],
          "G54430": ["12tribesofisrael"],
          "G24740": ["12tribesofisrael"],
          "H82630": ["test"],
          "H82620": ["abomination","test"],
          "H76260": ["12tribesofisrael"],
          "H88700": ["abomination","test"],
          "G14270": ["12tribesofisrael"],
          "H82510": ["abomination","test"],
          "H01893": ["abel"]
        }
        assert_object_equals_file(self, strongs_index, os.path.join(self.resources_dir, 'expected_strongs_index.json'))

    def test_map_usfm_by_global_search(self):
        usfm = read_file(os.path.join(self.resources_dir, 'usfm/41-MAT.usfm'))
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        locations_index = maptwtousfm3.indexWordsLocation(rc)
        strongs_index = maptwtousfm3.indexWordByStrongs(rc)
        mappedUSFM = maptwtousfm3.mapUSFMByGlobalSearch(usfm, rc, strongs_index, locations_index['false_positives'])
        expected_usfm = read_file(os.path.join(self.resources_dir, 'mapped_mat.usfm'))
        self.assertEqual(mappedUSFM, expected_usfm)

    def test_map_dir(self):
        rc = factory.load(os.path.join(self.resources_dir, 'tw_rc'))
        out_dir = os.path.join(self.temp_dir, 'mapped_usfm')
        maptwtousfm3.mapDir(os.path.join(self.resources_dir, 'usfm'), rc, out_dir)
        mapped_usfm = read_file(os.path.join(out_dir, '41-MAT.usfm'))
        expected_usfm = read_file(os.path.join(self.resources_dir, 'mapped_mat.usfm'))
        self.assertEqual(mapped_usfm, expected_usfm)

    def test_map_phrases(self):
        usfm = read_file(os.path.join(self.resources_dir, 'mapped_tit.usfm'))
        mapped_usfm = maptwtousfm3.mapPhrases(usfm)
        expected_usfm = read_file(os.path.join(self.resources_dir, 'mapped_phrases_tit.usfm'))
        self.assertEqual(mapped_usfm, expected_usfm)