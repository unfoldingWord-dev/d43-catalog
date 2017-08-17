from __future__ import unicode_literals

import codecs

import boto3

from libraries.tools.file_utils import write_file

"""
This is a separate file so it can be excluded from coverage testing on Travis.
This function will not run on Travis CI due to it needing AWS credentials.
"""

# TODO: add this to the d43-aws-tools library
def decrypt_file(source_file_name, destination_file_name):
    """
    Decrypts a file using the AWS encryption key 'signing_key'
    :param string source_file_name:
    :param string destination_file_name:
    :return: bool True if successful, otherwise False
    """
    client = boto3.client('kms')

    with codecs.open(source_file_name, 'rb') as in_file:
        data_bytes = in_file.read()

    response = client.decrypt(CiphertextBlob=data_bytes)

    if 'Plaintext' not in response:
        raise Exception('File not successfully decrypted: {}'.format(source_file_name))

    write_file(destination_file_name, response['Plaintext'])

    return True
