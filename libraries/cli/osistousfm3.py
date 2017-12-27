#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This tool reads an OSIS file and converts it into USFM3
"""

import argparse
import os
import sys
import xml.etree.ElementTree
import logging

from libraries.tools.file_utils import write_file

LOGGER_NAME='convert_osis_to_usfm'

def getLemma(lexicon, strong):
    """
    Retrieves the lemma from the lexicon using the strong's number as the key
    :param lexicon:
    :type lexicon: xml.etree.ElementTree
    :param strong:
    :return:
    """
    if lexicon:
        for entry in lexicon:
            if entry.tag.endswith('}entry') and 'id' in entry.attrib and entry.attrib['id'].lower() == strong.lower():
                for element in entry:
                    if element.tag.endswith('}w'):
                        return element.text

    return None

def convertFile(lang, osis_file, lexicon):
    """
    Converts an OSIS file to USFM3
    :param lang: the language represented in the OSIS file
    :param osis_file: the OSIS file to be converted to USFM
    :return: a usfm string
    """
    logger = logging.getLogger(LOGGER_NAME)
    if sys.version_info >= (3,0,0):
        raise Exception('Only python 2.7 is supported')

    usfm = []
    root = xml.etree.ElementTree.parse(osis_file).getroot()
    books = getXmlBooks(root)
    if len(books) > 1:
        logger.error('Found {} books in {} but expected 1'.format(len(books), osis_file))
        return None
    if not len(books):
        logger.warn('No books found in {}'.format(len(books), osis_file))
        return None

    book = books[0]
    bookId = book.attrib['osisID']
    # header
    for chapter in book:
        chapterId = chapter.attrib['osisID']
        chapterNum = int(chapterId.split('.')[1])

        # chapter
        usfm.append('')
        usfm.append('\\c {}'.format(chapterNum))
        usfm.append('\\p')

        for verse in chapter:
            verseId = verse.attrib['osisID']
            verseNum = int(verseId.split('.')[2])

            # verse
            usfm.append('')
            usfm.append('\\v {}'.format(verseNum))
            for word in verse:

                # word
                if word.tag.endswith('}seg'):
                    usfm.append(word.text)
                else:
                    usfm.append(convertWord(word))

    return '\n'.join(usfm)

def convertWord(word):
    logger = logging.getLogger(LOGGER_NAME)
    morph = ''
    if 'morph' in word.attrib:
        morph = word.attrib['morph']
    else:
        logger.warn('Missing morph in {}'.format(word))
    lemma = ''
    if 'lemma' in word.attrib:
        lemma = word.attrib['lemma'].decode('utf-8')
    else:
        logger.warn('Missing lemma in {}'.format(word))
    return u'{}\w {}|lemma="{}" strong="G{}" x-morph="Gr,{}{}{}"\w*{}'.format(
        '',
        word.text,#.decode('utf-8'),
        lemma,
        ''.zfill(5),
        '',
        morph,
        '',
        ''
    )

def getXmlBooks(xml):
    """
    Returns a list of book xml trees found within the xml.
    Books without any children will be ignored
    :param xml: osis xml
    :type xml: xml.etree.ElementTree
    :return:
    """
    if not len(xml):
        return []
    if 'type' in xml.attrib and xml.attrib['type'] == 'book':
        return [xml]
    books = []
    for child in xml:
        books += getXmlBooks(child)
    return books


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

    errors_log_file = os.path.join(args.output, 'errors.log')
    if os.path.isfile(errors_log_file):
        os.remove(errors_log_file)

    # configure logger
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.WARNING)
    handler = logging.FileHandler(errors_log_file)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    convertDir()

    # TODO: list files in directory and process
    # osis_books = convert(args.lang, args.input)
    #
    # for book in osis_books:
    #     file_path = os.path.join(args.output, '{}-{}.usfm'.format(book['sort'], book['id']))
    #     write_file(file_path, book['usfm'])