from libraries.tools.ts_v2_utils import build_json_source_from_usx, build_usx
from libraries.tools.versification import  hebrew_to_ufw
from unittest import TestCase
import tempfile
import os
import shutil
import yaml
from libraries.tools.file_utils import download_rc, read_file, remove


class TestVersification(TestCase):
    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='test_versification_')

    def tearDown(self):
        # clean up local temp files
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gen_32_1_is_31_55(self):
        book = 'gen'
        ref = hebrew_to_ufw(book, 32, 1)
        expected = {'book': book, 'chapter': 31, 'verse': 55}
        self.assertEqual(expected, ref.to_dict())

    def test_exo_7_26_is_8_1(self):
        book = 'exo'
        ref = hebrew_to_ufw(book, 7, 26)
        expected = {'book': book, 'chapter': 8, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_exo_21_37_is_22_1(self):
        book = 'exo'
        ref = hebrew_to_ufw(book, 21, 37)
        expected = {'book': book, 'chapter': 22, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_lev_5_20_is_6_1(self):
        book = 'lev'
        ref = hebrew_to_ufw(book, 5, 20)
        expected = {'book': book, 'chapter': 6, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_num_17_1_is_16_36(self):
        book = 'num'
        ref = hebrew_to_ufw(book, 17, 1)
        expected = {'book': book, 'chapter': 16, 'verse': 36}
        self.assertEqual(expected, ref.to_dict())

    def test_num_30_1_is_29_40(self):
        book = 'num'
        ref = hebrew_to_ufw(book, 30, 1)
        expected = {'book': book, 'chapter': 29, 'verse': 40}
        self.assertEqual(expected, ref.to_dict())

    def test_deu_13_1_is_12_32(self):
        book = 'deu'
        ref = hebrew_to_ufw(book, 13, 1)
        expected = {'book': book, 'chapter': 12, 'verse': 32}
        self.assertEqual(expected, ref.to_dict())

    def test_deu_23_1_is_22_30(self):
        book = 'deu'
        ref = hebrew_to_ufw(book, 23, 1)
        expected = {'book': book, 'chapter': 22, 'verse': 30}
        self.assertEqual(expected, ref.to_dict())

    def test_deu_28_69_is_29_1(self):
        book = 'deu'
        ref = hebrew_to_ufw(book, 28, 69)
        expected = {'book': book, 'chapter': 29, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_1sa_20_42_is_20_42(self):
        book = '1sa'
        ref = hebrew_to_ufw(book, 20, 42)
        expected = {'book': book, 'chapter': 20, 'verse': 42}
        self.assertEqual(expected, ref.to_dict())

    def test_1sa_21_1_is_20_42(self):
        book = '1sa'
        ref = hebrew_to_ufw(book, 21, 1)
        expected = {'book': book, 'chapter': 20, 'verse': 42}
        self.assertEqual(expected, ref.to_dict())

    def test_1sa_24_1_is_23_29(self):
        book = '1sa'
        ref = hebrew_to_ufw(book, 24, 1)
        expected = {'book': book, 'chapter': 23, 'verse': 29}
        self.assertEqual(expected, ref.to_dict())

    def test_2sa_19_1_is_18_33(self):
        book = '2sa'
        ref = hebrew_to_ufw(book, 19, 1)
        expected = {'book': book, 'chapter': 18, 'verse': 33}
        self.assertEqual(expected, ref.to_dict())

    def test_1ki_5_1_is_4_21(self):
        book = '1ki'
        ref = hebrew_to_ufw(book, 5, 1)
        expected = {'book': book, 'chapter': 4, 'verse': 21}
        self.assertEqual(expected, ref.to_dict())

    def test_1ki_22_43_is_22_43(self):
        book = '1ki'
        ref = hebrew_to_ufw(book, 22, 43)
        expected = {'book': book, 'chapter': 22, 'verse': 43}
        self.assertEqual(expected, ref.to_dict())

    def test_1ki_22_44_is_22_43(self):
        book = '1ki'
        ref = hebrew_to_ufw(book, 22, 44)
        expected = {'book': book, 'chapter': 22, 'verse': 43}
        self.assertEqual(expected, ref.to_dict())

    def test_2ki_12_1_is_11_21(self):
        book = '2ki'
        ref = hebrew_to_ufw(book, 12, 1)
        expected = {'book': book, 'chapter': 11, 'verse': 21}
        self.assertEqual(expected, ref.to_dict())

    def test_1ch_5_27_is_6_1(self):
        book = '1ch'
        ref = hebrew_to_ufw(book, 5, 27)
        expected = {'book': book, 'chapter': 6, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_1ch_12_4_is_12_4(self):
        book = '1ch'
        ref = hebrew_to_ufw(book, 12, 4)
        expected = {'book': book, 'chapter': 12, 'verse': 4}
        self.assertEqual(expected, ref.to_dict())

    def test_1ch_12_5_is_12_4(self):
        book = '1ch'
        ref = hebrew_to_ufw(book, 12, 5)
        expected = {'book': book, 'chapter': 12, 'verse': 4}
        self.assertEqual(expected, ref.to_dict())

    def test_2ch_1_18_is_2_1(self):
        book = '2ch'
        ref = hebrew_to_ufw(book, 1, 18)
        expected = {'book': book, 'chapter': 2, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_2ch_13_23_is_14_1(self):
        book = '2ch'
        ref = hebrew_to_ufw(book, 13, 23)
        expected = {'book': book, 'chapter': 14, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_neh_3_33_is_4_1(self):
        book = 'neh'
        ref = hebrew_to_ufw(book, 3, 33)
        expected = {'book': book, 'chapter': 4, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    # def test_neh_7_67(self):
        # NOTE: we don't currently support splitting into ufw
        # pass

    def test_neh_10_1_is_9_38(self):
        book = 'neh'
        ref = hebrew_to_ufw(book, 10, 1)
        expected = {'book': book, 'chapter': 9, 'verse': 38}
        self.assertEqual(expected, ref.to_dict())

    def test_job_40_25_is_41_1(self):
        book = 'job'
        ref = hebrew_to_ufw(book, 40, 25)
        expected = {'book': book, 'chapter': 41, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_psa_deletions(self):
        # TODO: test deletions
        pass

    # def test_psa_13_6(self):
        # NOTE: we don't currently support splitting into ufw
        # pass

    # def test_psa_66_2(self):
        # NOTE: we don't currently support splitting into ufw
        # pass

    def test_ecc_4_17_is_5_1(self):
        book = 'ecc'
        ref = hebrew_to_ufw(book, 4, 17)
        expected = {'book': book, 'chapter': 5, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_sng_7_1_is_6_13(self):
        book = 'sng'
        ref = hebrew_to_ufw(book, 7, 1)
        expected = {'book': book, 'chapter': 6, 'verse': 13}
        self.assertEqual(expected, ref.to_dict())

    def test_isa_8_23_is_9_1(self):
        book = 'isa'
        ref = hebrew_to_ufw(book, 8, 23)
        expected = {'book': book, 'chapter': 9, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    # def test_isa_63_19(self):
        # NOTE: we don't currently support splitting into ufw
        # pass

    def test_jer_8_23_is_9_1(self):
        book = 'jer'
        ref = hebrew_to_ufw(book, 8, 23)
        expected = {'book': book, 'chapter': 9, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_ezk_21_1_is_20_45(self):
        book = 'ezk'
        ref = hebrew_to_ufw(book, 21, 1)
        expected = {'book': book, 'chapter': 20, 'verse': 45}
        self.assertEqual(expected, ref.to_dict())

    def test_dan_3_31_is_4_1(self):
        book = 'dan'
        ref = hebrew_to_ufw(book, 3, 31)
        expected = {'book': book, 'chapter': 4, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_dan_6_1_is_5_31(self):
        book = 'dan'
        ref = hebrew_to_ufw(book, 6, 1)
        expected = {'book': book, 'chapter': 5, 'verse': 31}
        self.assertEqual(expected, ref.to_dict())

    def test_hos_2_1_is_1_10(self):
        book = 'hos'
        ref = hebrew_to_ufw(book, 2, 1)
        expected = {'book': book, 'chapter': 1, 'verse': 10}
        self.assertEqual(expected, ref.to_dict())

    def test_hos_12_1_is_11_12(self):
        book = 'hos'
        ref = hebrew_to_ufw(book, 12, 1)
        expected = {'book': book, 'chapter': 11, 'verse': 12}
        self.assertEqual(expected, ref.to_dict())

    def test_hos_14_1_is_13_16(self):
        book = 'hos'
        ref = hebrew_to_ufw(book, 14, 1)
        expected = {'book': book, 'chapter': 13, 'verse': 16}
        self.assertEqual(expected, ref.to_dict())

    def test_jol_3_1_is_2_28(self):
        book = 'jol'
        ref = hebrew_to_ufw(book, 3, 1)
        expected = {'book': book, 'chapter': 2, 'verse': 28}
        self.assertEqual(expected, ref.to_dict())

    def test_jon_2_1_is_1_17(self):
        book = 'jon'
        ref = hebrew_to_ufw(book, 2, 1)
        expected = {'book': book, 'chapter': 1, 'verse': 17}
        self.assertEqual(expected, ref.to_dict())

    def test_mic_4_14_is_5_1(self):
        book = 'mic'
        ref = hebrew_to_ufw(book, 4, 14)
        expected = {'book': book, 'chapter': 5, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_nah_2_1_is_1_15(self):
        book = 'nah'
        ref = hebrew_to_ufw(book, 2, 1)
        expected = {'book': book, 'chapter': 1, 'verse': 15}
        self.assertEqual(expected, ref.to_dict())

    def test_zec_2_1_is_1_18(self):
        book = 'zec'
        ref = hebrew_to_ufw(book, 2, 1)
        expected = {'book': book, 'chapter': 1, 'verse': 18}
        self.assertEqual(expected, ref.to_dict())

    def test_mal_3_19_is_4_1(self):
        book = 'mal'
        ref = hebrew_to_ufw(book, 3, 19)
        expected = {'book': book, 'chapter': 4, 'verse': 1}
        self.assertEqual(expected, ref.to_dict())

    def test_processing_hbo(self):
        """
        Test downloading and processing some hebrew
        :return:
        """
        return
        rc_dir = download_rc('hbo', 'uhb', 'https://cdn.door43.org/hbo/uhb/v2.1.1/uhb.zip', self.temp_dir)

        manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
        usx_dir = os.path.join(rc_dir, 'usx')
        for project in manifest['projects']:
            pid = project['identifier']

            # copy usfm project file
            usfm_dir = os.path.join(self.temp_dir, 'usfm')
            if not os.path.exists(usfm_dir):
                os.makedirs(usfm_dir)
            usfm_dest_file = os.path.normpath(os.path.join(usfm_dir, project['path']))
            usfm_src_file = os.path.normpath(os.path.join(rc_dir, project['path']))
            shutil.copyfile(usfm_src_file, usfm_dest_file)

            # transform usfm to usx
            build_usx(usfm_dir, usx_dir)

            # clean up converted usfm file
            remove(usfm_dest_file, True)

            # convert USX to JSON
            path = os.path.normpath(os.path.join(usx_dir, '{}.usx'.format(pid.upper())))
            source = build_json_source_from_usx(path, 'hbo', pid, '2019')