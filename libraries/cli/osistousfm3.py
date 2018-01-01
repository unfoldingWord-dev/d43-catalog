#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This tool reads an OSIS file and converts it into USFM3
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree
import logging
import json

from libraries.tools.file_utils import write_file
from libraries.tools.book_data import get_book_by_osis_id

LOGGER_NAME='convert_osis_to_usfm'

def getLemma(lexicon, strong):
    """
    Retrieves the lemma from the lexicon using the strong's number as the key
    :param lexicon:
    :type lexicon: json
    :param strong:
    :return:
    """

    if lexicon and strong.upper() in lexicon:
        return lexicon[strong.upper()]

    return None

def indexLexicon(lexicon):
    """
    Indexes the lexicon so we can perform faster queries
    :param lexicon:
    :return:
    """
    index = {}
    if lexicon:
        for entry in lexicon:
            if entry.tag.endswith('}entry'):
                strong, lemma = indexLexiconEntry(entry)
                if strong and lemma:
                    index[strong.upper()] = lemma
    return index

def indexLexiconEntry(entry):
    """
    Retrieves the strong number and lemma from an entry if it is valid
    :param entry:
    :return:
    """
    if 'id' in entry.attrib:
        for element in entry:
            if element.tag.endswith('}w'):
                return entry.attrib['id'], element.text
    return None, None

def convertFile(osis_file, lexicon):
    """
    Converts an OSIS file to USFM3
    :param osis_file: the OSIS file to be converted to USFM
    :param lexicon:
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

    usfm.append('\\id {}'.format(bookId.upper()))
    usfm.append('\\ide UTF-8')

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
                if word.tag.endswith('}w'):
                    usfm.append(convertWord(lexicon, word, '{} {}:{}'.format(bookId, chapterNum, verseNum)))
                elif word.tag.endswith('}seg') and word.text is not None:
                    if len(usfm) > 0:
                        usfm[-1] = u'{}{}'.format(usfm[-1], word.text)
                    else:
                        usfm.append(word.text)
                else:
                    logger.debug('unknown xml tag "{}"'.format(word.tag))

    return u'\n'.join(usfm)

def convertWord(lexicon, word, passage=''):
    """
    Converts an osis word to usfm3
    :param lexicon:
    :param word:
    :param passage: used for reporting errors.
    :return:
    """
    logger = logging.getLogger(LOGGER_NAME)
    morph = ''
    strong = ''
    formatted_strong = ''

    if 'morph' in word.attrib:
        morph = word.attrib['morph']
        if morph[0] == 'H':
            morph = 'He,{}'.format(morph[1:])
        elif morph[0] == 'A':
            morph = 'Ar,{}'.format(morph[1:])
        else:
            raise Exception('Unknown language in morph at {}'.format(passage))
        morph = morph.replace('/', ':')
    # TRICKY: the lemma field contains the strong number
    if 'lemma' in word.attrib:
        strong, formatted_strong = parseStrong(word.attrib['lemma'].decode('utf-8'))
    else:
        logger.warn('Missing lemma in {} at {}'.format(word.text, passage))
    # TRICKY: look up the actual lemma from the strong
    lemma = getLemma(lexicon, 'H{}'.format(strong))
    if not lemma:
        lemma = ''
        logger.error('No match in lexicon for strong\'s "{}" at  {}'.format(word.attrib['lemma'].decode('utf-8'), passage))
    text = re.sub(r'/', u'\u200B', word.text)

    if morph:
        # validate morph and word component count
        if text.count(u'\u200b') != morph.count(':'):
            logger.warning('Word and morph components are not aligned at {}'.format(passage))
        return u'\w {}|lemma="{}" strong="{}" x-morph="{}" \w*'.format(
            text,
            lemma,
            formatted_strong,
            morph
        )
    else:
        return u'\w {}|lemma="{}" strong="{}" \w*'.format(
            text,
            lemma,
            formatted_strong
        )

def parseStrong(str):
    """
    Parses the strong number from a string
    :param str:
    :return:
    """
    strong = str
    strong = re.sub(r'^([a-z]+/)+', '', strong.lower())
    strong = re.sub(r'(\s*[a-z]+)+$', '', strong.lower())

    formatted = str.replace(strong, 'H{}'.format(strong.zfill(5)))
    formatted = re.sub(r'/', ':', formatted)
    return strong, formatted

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


def convertDir(in_dir, out_dir, lexicon):
    """
    Converts a directory of osis files to usfm
    :param in_dir:
    :param out_dir:
    :param lexicon:
    :return:
    """
    logger = logging.getLogger(LOGGER_NAME)

    if os.path.isfile(in_dir):
        raise Exception('Input must be a directory')
    input_files = []
    for root, dirs, files in os.walk(in_dir):
        input_files.extend(files)
        break

    for file_name in input_files:
        if file_name.lower() == 'versemap.xml' or (not file_name.endswith('.xml') and not file_name.endswith('.osis')):
            print('Skipping file {}'.format(file_name))
            continue
        print('Processing {}...'.format(file_name))
        usfm = convertFile(os.path.join(in_dir, file_name), lexicon)
        book_id = os.path.splitext(file_name)[0]
        book_meta = get_book_by_osis_id(book_id)
        if book_meta:
            out_file = os.path.join(out_dir, '{}-{}.usfm'.format(book_meta['sort'], book_meta['usfm_id']))
            write_file(out_file, usfm)
        else:
            message = 'Missing book meta data for {}'.format(book_id)
            print(message)
            logger.error(message)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-l', '--lex', dest='lexicon', required=True, help='The lexicon for mapping strong numbers to the lemma. The Hebrew lexicon is available at https://github.com/openscriptures/HebrewLexicon/blob/master/HebrewStrong.xml')
    parser.add_argument('-i', '--input', dest='input', required=True, help='OSIS file to convert')
    parser.add_argument('-o', '--output', dest='output', required=True, help='Directory where to save the generated USFM')

    args = parser.parse_args(sys.argv[1:])
    if os.path.isfile(args.input):
        raise Exception('Input must be a directory')
    if os.path.isfile(args.output):
        raise Exception('Output must be a directory')

    if not os.path.isdir(args.output):
        os.makedirs(args.output)

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

    print('Loading lexicon...')
    lexicon = xml.etree.ElementTree.parse(args.lexicon).getroot()
    lex_index = indexLexicon(lexicon)
    convertDir(args.input, args.output, lex_index)


    # announce errors or clean up log file
    if os.path.isfile(errors_log_file):
        statinfo = os.stat(errors_log_file)
        if statinfo.st_size > 0:
            print('WARNING: errors were detected. See {} for details'.format(errors_log_file))
        else:
            os.remove(errors_log_file)

    print('Finished')