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

    def test_joel_3_1(self):
        ref = hebrew_to_ufw('jol', 3, 1)
        expected = {'book': 'jol', 'chapter': 2, 'verse': 28}
        self.assertEqual(expected, ref.to_dict())

    def test_me(self):
        """
        Test downloading and processing some hebrew
        :return:
        """
        # return
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