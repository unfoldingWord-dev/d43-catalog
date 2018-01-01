#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This tool reads a CSV file containing a list of words and converts it into USFM3 with word level attributes.
This currently expects the Greek New Testament.
"""

import argparse
import csv
import os
import sys
import re

from libraries.tools.file_utils import write_file
from libraries.tools.book_data import get_book_by_sort

def convert(lang, csv_file):
    """
    Converts a CSV file to USFM3
    :param lang: the language of the words in the CSV file
    :param csv_file: the csv to be converted to USFM
    :return:
    """
    if sys.version_info >= (3,0,0):
        raise Exception('Only python 2.7 is supported')
    with open(csv_file) as file:
        books = []
        usfm = []
        csvreader = csv.DictReader(file)
        lastverse = None
        lastchapter = None
        lastbook = None
        for row in csvreader:
            row_usfm = convert_row(lang, row)
            if not row_usfm: continue

            # insert verse marker
            ref = row['VERSE']
            book_sort = apply_nt_offset(ref[:2])
            book_id = get_book_by_sort(book_sort)['usfm_id']
            book_name = get_book_by_sort(book_sort)['en_name']
            chp = ref[2:4]
            vrs = ref[4:6]

            if not lastbook or book_sort != lastbook:
                if lastbook and len(usfm):
                    # close last book
                    last_book_id = get_book_by_sort(lastbook)['usfm_id']
                    books.append({
                        'sort': lastbook,
                        'id': last_book_id,
                        'usfm': '\n'.join(usfm)
                    })
                    usfm = []
                lastchapter = None
                print('INFO: Processing {}'.format(book_id))
                usfm.append('\\id {} {}'.format(book_id.upper(), book_name))
                usfm.append('\\ide UTF-8')
                usfm.append('\\h {}'.format(book_name))
                usfm.append('\\toc1')
                usfm.append('\\toc2 {}'.format(book_name))
                usfm.append('\\toc3 {}{}'.format(book_id[:1].upper(), book_id[1:].lower())) # e.g. Gen
                usfm.append('\\mt {}'.format(book_name))

            if not lastchapter or chp > lastchapter:
                lastverse = None
                usfm.append('')
                usfm.append('\\c {}'.format(int(chp)))
                usfm.append('\\p')

            if not lastverse or vrs > lastverse:
                usfm.append('')
                usfm.append('\\v {}'.format(int(vrs)))

            lastbook = book_sort
            lastchapter = chp
            lastverse = vrs

            usfm.append(row_usfm)
        if len(usfm):
            # close last book
            last_book_id = get_book_by_sort(lastbook)['usfm_id']
            books.append({
                'sort': lastbook,
                'id': last_book_id,
                'usfm': '\n'.join(usfm)
            })
            usfm = []
        return books

def convert_row(lang, row):
    """
    Converts a single CSV row to USFM3
    :param lang: the language of the word
    :param row: a row from a CSV file
    :return: the generated USFM3
    """
    opening_punctuation, closing_punctuation = split_puncuation(row['PUNC'].decode('utf-8'))
    return u'{}\w {}|lemma="{}" strong="G{}" x-morph="Gr,{}{}{}"\w*{}'.format(
        opening_punctuation,
        row['UMEDIEVAL'].decode('utf-8'),
        row['ULEMMA'].decode('utf-8'),
        row['LEXEME'].zfill(5),
        row['SYN'].replace('.', ','),
        row['MORPH'].replace('.', ','),
        row['LEX'].replace('.', ','),
        closing_punctuation
    )

def split_puncuation(punctuation):
    """
    Separates the punctuation into opening and closing groups.

    :param punctuation:
    :return: a tuple containing the opening and closing punctuation
    """
    opening_characters = [u'¶', u'“']
    opening = []
    closing = []
    for char in punctuation:
        if char in opening_characters:
            if char == u'¶': char = '\\p\n' # make usfm paragraph
            opening.append(char)
        else:
            closing.append(char)
    return ''.join(opening), ''.join(closing)

def apply_nt_offset(book_id):
    """
    Offsets the book id to to the new testament equivalent.
    e.g. 01 becomes 41 (Matthew)
    :param book_id:
    :return:
    """
    return '{}'.format(int(book_id) + 40).zfill(2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-l', '--lang', dest='lang', required=True, help='The language represented in the CSV file')
    parser.add_argument('-i', '--input', dest='input', required=True, help='CSV file to convert')
    parser.add_argument('-o', '--output', dest='output', required=True, help='Directory where to save the generated USFM')

    args = parser.parse_args(sys.argv[1:])
    if os.path.isfile(args.output):
        raise Exception('Output must be a directory')

    usfm_books = convert(args.lang, args.input)

    for book in usfm_books:
        file_path = os.path.join(args.output, '{}-{}.usfm'.format(book['sort'], book['id']))
        write_file(file_path, book['usfm'])