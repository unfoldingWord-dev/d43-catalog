import os
import shlex
import codecs
import tempfile
import shutil
import inspect
import json
from tools.url_utils import download_file
from tools.file_utils import write_file
from base64 import b64decode
from subprocess import Popen, PIPE
from aws_decrypt import decrypt_file

class Signer(object):

    def __init__(self, default_pem_path=None):
        """
        Initialize a new signer object
        :param string default_pem_path: path to the default pem. This should be encrypted by aws.
        """
        self.default_enc_pem = default_pem_path

    def sign_file(self, file_to_sign, pem_file=None):
        """
        Generates a .sig file and returns the full file name of the .sig file
        :param str|unicode file_to_sign:
        :param str|unicode|None pem_file:
        :return: str|unicode The full file name of the .sig file
        """
        # if pem file was not passed, use the default one
        if not pem_file:
            pem_file = self._get_default_pem_file()

        print(pem_file)

        # # read the file contents
        # with codecs.open(file_to_sign, 'r', encoding='utf-8') as in_file:
        #     content = in_file.read()

        # use openssl to sign the content
        sha384_file = file_to_sign + '.sha384'
        sign_com = 'openssl dgst -sha384 -sign {0} -out {1} {2}'.format(pem_file, sha384_file, file_to_sign)
        command = shlex.split(sign_com)
        com = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        out, err = com.communicate()

        if err:
            raise Exception(err)

        # base64 encode the signature
        file_name_without_extension = os.path.splitext(file_to_sign)[0]
        sig_file_name = '{}.sig'.format(file_name_without_extension)
        sign_com = 'openssl base64 -in {0} -out {1}'.format(sha384_file, sig_file_name)
        command = shlex.split(sign_com)
        com = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        out, err = com.communicate()

        if err:
            raise Exception(err)

        # get the base64 encoded signature
        with codecs.open(sig_file_name, 'r', encoding='utf-8') as in_file:
            signed_content = in_file.read()

        # save the signed content
        file_content = []
        signature = {'si': 'uW', 'sig': signed_content}
        file_content.append(signature)
        write_file(sig_file_name, file_content)

        return sig_file_name

    def verify_signature(self, content_file, sig_file, pem_file=None):
        """
        Verify that the file content has not changed since it was signed
        :param str|unicode content_file:
        :param str|unicode sig_file:
        :param str|unicode|None pem_file: If left null the default pem file will be used
        :return:
        """

        temp_dir = tempfile.mkdtemp(prefix='tempVerify_')

        try:

            # if pem file was not passed, use the default one
            if not pem_file:
                pem_file = os.path.join(temp_dir, 'uW-vk.pem')
                download_file('https://pki.unfoldingword.org/uW-vk.pem', pem_file)

            # get the uW signature from the sig file
            with codecs.open(sig_file, 'r', 'utf-8-sig') as in_file:
                sig_file_content = json.loads(in_file.read())

            signature = [x['sig'] for x in sig_file_content if x['si'] == 'uW'][0]
            signature_path = os.path.join(temp_dir, 'signature.sig')

            # save the signature to a temp file
            with open(signature_path, str('w')) as out_file:
                out_file.write(b64decode(signature))

            # Use openssl to verify signature
            command_str = 'openssl dgst -sha384 -verify {0} -signature {1} {2}'.format(pem_file, signature_path,
                                                                                       content_file)
            command = shlex.split(command_str)
            com = Popen(command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            out, err = com.communicate()

            if com.returncode == 0:
                return True

            raise RuntimeError(err)

        finally:
            # clean up temp dir, if used
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _get_default_pem_file(self):
        """
        Decrypts the default pem file provided with the lambda and returns the full file name
        :return: str|unicode
        """
        if not self.default_enc_pem:
            raise Exception('No default pem was specified')

        pem_file = os.path.join(tempfile.gettempdir(), 'uW-sk.pem')
        result = decrypt_file(self.default_enc_pem, pem_file)

        if not result:
            raise Exception('Not able to decrypt the pem file.')

        return pem_file