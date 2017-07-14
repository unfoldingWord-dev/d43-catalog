import os
import shlex
import codecs
import tempfile
import shutil
import json
from tools.url_utils import download_file
from tools.file_utils import write_file
from base64 import b64decode
from subprocess import Popen, PIPE
from aws_decrypt import decrypt_file

class Signer(object):

    def __init__(self, priv_pem_path=None, pub_pem_path=None):
        """
        Initialize a new signer object
        :param string priv_pem_path: path to the default private pem file. If encrypted (has .enc extension) it will be decrypted by aws
        :param string pub_pem_path: path to the default public pem file.
        """
        self.priv_pem = priv_pem_path
        self.pub_pem = pub_pem_path
        self.temp_dir = tempfile.mkdtemp(prefix='signer_')

    def __del__(self):
        shutil.rmtree(self.temp_dir)

    def sign_file(self, file_to_sign, private_pem_file=None):
        """
        Generates a .sig file and returns the full file name of the .sig file
        :param str|unicode file_to_sign:
        :param str|unicode|None private_pem_file:
        :return: str|unicode The full file name of the .sig file
        """
        # if pem file was not passed, use the default one
        if not private_pem_file:
            private_pem_file = self._default_priv_pem()

        print(private_pem_file)

        # use openssl to sign the content
        sha384_file = file_to_sign + '.sha384'
        sign_com = 'openssl dgst -sha384 -sign {0} -out {1} {2}'.format(private_pem_file, sha384_file, file_to_sign)
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

    def verify_signature(self, content_file, sig_file, public_pem_file=None):
        """
        Verify that the file content has not changed since it was signed
        :param str|unicode content_file:
        :param str|unicode sig_file:
        :param str|unicode|None public_pem_file: If left null the default pem file will be used
        :return:
        """

        temp_dir = tempfile.mkdtemp(prefix='tempVerify_')

        try:

            # if pem file was not passed, use the default one
            if not public_pem_file:
                public_pem_file = self._default_pub_pem()

            # get the uW signature from the sig file
            with codecs.open(sig_file, 'r', 'utf-8-sig') as in_file:
                sig_file_content = json.loads(in_file.read())

            signature = [x['sig'] for x in sig_file_content if x['si'] == 'uW'][0]
            signature_path = os.path.join(temp_dir, 'signature.sig')

            # save the signature to a temp file
            with open(signature_path, str('w')) as out_file:
                out_file.write(b64decode(signature))

            # Use openssl to verify signature
            command_str = 'openssl dgst -sha384 -verify {0} -signature {1} {2}'.format(public_pem_file, signature_path,
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

    def _default_priv_pem(self):
        """
        Returns the path to the default private pem.
        If the pem is encrypted (has an extension .enc) it will be decrypted by aws
        :return: str|unicode
        """
        if not self.priv_pem:
            raise Exception('No default private pem was specified')

        if self.priv_pem.endswith('.enc'):
            # decrypt pem
            pem_file = os.path.join(tempfile.gettempdir(), 'uW-sk.pem')
            result = decrypt_file(self.priv_pem, pem_file)
            if not result:
                raise Exception('Not able to decrypt the pem file.')

            return pem_file
        else:
            return self.priv_pem

    def _default_pub_pem(self):
        """
        Returns the path to the default public pem.
        If a default has not been manually specified then the aws pem will be downloaded
        :return:
        """
        if not self.pub_pem:
            print('INFO: retrieving public pem from AWS')
            pem_path = os.path.join(self.temp_dir, 'uW-vk.pem')
            download_file('https://pki.unfoldingword.org/uW-vk.pem', pem_path)
            self.pub_pem = pem_path

        return self.pub_pem
