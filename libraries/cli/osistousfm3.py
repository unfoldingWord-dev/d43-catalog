#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This tool reads an OSIS file and converts it into USFM3
"""

import argparse
import os
import sys
import xml.etree.ElementTree

from libraries.tools.file_utils import write_file

def convertFile(lang, osis_file):
    """
    Converts an OSIS file to USFM3
    :param lang: the language represented in the OSIS file
    :param osis_file: the OSIS file to be converted to USFM
    :return:
    """
    if sys.version_info >= (3,0,0):
        raise Exception('Only python 2.7 is supported')
    with open(osis_file) as file:
        usfm = u''
        tree = xml.etree.ElementTree.parse(osis_file).getroot()
        # TODO: parse xml and remove word attributes and links
        return usfm

def convertDir():
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-l', '--lang', dest='lang', required=True, help='The language represented in the OSIS file')
    parser.add_argument('-i', '--input', dest='input', required=True, help='OSIS file to convert')
    parser.add_argument('-o', '--output', dest='output', required=True, help='Directory where to save the generated USFM')

    args = parser.parse_args(sys.argv[1:])
    if os.path.isfile(args.input):
        raise Exception('Input must be a directory')
    if os.path.isfile(args.output):
        raise Exception('Output must be a directory')

    convertDir()

    # TODO: list files in directory and process
    # osis_books = convert(args.lang, args.input)
    #
    # for book in osis_books:
    #     file_path = os.path.join(args.output, '{}-{}.usfm'.format(book['sort'], book['id']))
    #     write_file(file_path, book['usfm'])