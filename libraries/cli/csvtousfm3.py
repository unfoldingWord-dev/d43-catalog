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
            book_id = book_identifiers[book_sort]['id']
            book_name = book_identifiers[book_sort]['en_name']
            chp = ref[2:4]
            vrs = ref[4:6]

            if not lastbook or book_sort != lastbook:
                if lastbook and len(usfm):
                    # close last book
                    last_book_id = book_identifiers[lastbook]['id']
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
            last_book_id = book_identifiers[lastbook]['id']
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


def append_passage_reference(usfm, ref, lastbook, lastchapter, lastverse):
    """
    Appends the passage reference to the usfm object as needed
    :param usfm:
    :param ref: the passage reference e.g. the 'VERSE' column
    :param lastbook: the last seen book
    :param lastchapter: the last seen chapter
    :param lastverse: the last seen verse
    :return:
    """
    pass

book_identifiers = {
    '01': {'id': 'GEN', 'en_name': 'Genesis'},
    '02': {'id': 'EXO', 'en_name': 'Exodus'},
    '03': {'id': 'LEV', 'en_name': 'Leviticus'},
    '04': {'id': 'NUM', 'en_name': 'Numbers'},
    '05': {'id': 'DEU', 'en_name': 'Deuteronomy'},
    '06': {'id': 'JOS', 'en_name': 'Joshua'},
    '07': {'id': 'JDG', 'en_name': 'Judges'},
    '08': {'id': 'RUT', 'en_name': 'Ruth'},
    '09': {'id': '1SA', 'en_name': '1 Samuel'},
    '10': {'id': '2SA', 'en_name': '2 Samuel'},
    '11': {'id': '1KI', 'en_name': '1 Kings'},
    '12': {'id': '2KI', 'en_name': '2 Kings'},
    '13': {'id': '1CH', 'en_name': '1 Chronicles'},
    '14': {'id': '2CH', 'en_name': '2 Chronicles'},
    '15': {'id': 'EZR', 'en_name': 'Ezra'},
    '16': {'id': 'NEH', 'en_name': 'Nehemiah'},
    '17': {'id': 'EST', 'en_name': 'Esther (Hebrew)'},
    '18': {'id': 'JOB', 'en_name': 'Job'},
    '19': {'id': 'PSA', 'en_name': 'Psalms'},
    '20': {'id': 'PRO', 'en_name': 'Proverbs'},
    '21': {'id': 'ECC', 'en_name': 'Ecclesiastes'},
    '22': {'id': 'SNG', 'en_name': 'Song of Songs'},
    '23': {'id': 'ISA', 'en_name': 'Isaiah'},
    '24': {'id': 'JER', 'en_name': 'Jeremiah'},
    '25': {'id': 'LAM', 'en_name': 'Lamentations'},
    '26': {'id': 'EZK', 'en_name': 'Ezekiel'},
    '27': {'id': 'DAN', 'en_name': 'Daniel (Hebrew)'},
    '28': {'id': 'HOS', 'en_name': 'Hosea'},
    '29': {'id': 'JOL', 'en_name': 'Joel'},
    '30': {'id': 'AMO', 'en_name': 'Amos'},
    '31': {'id': 'OBA', 'en_name': 'Obadiah'},
    '32': {'id': 'JON', 'en_name': 'Jonah'},
    '33': {'id': 'MIC', 'en_name': 'Micah'},
    '34': {'id': 'NAM', 'en_name': 'Nahum'},
    '35': {'id': 'HAB', 'en_name': 'Habakkuk'},
    '36': {'id': 'ZEP', 'en_name': 'Zephaniah'},
    '37': {'id': 'HAG', 'en_name': 'Haggai'},
    '38': {'id': 'ZEC', 'en_name': 'Zechariah'},
    '39': {'id': 'MAL', 'en_name': 'Malachi'},
    '41': {'id': 'MAT', 'en_name': 'Matthew'},
    '42': {'id': 'MRK', 'en_name': 'Mark'},
    '43': {'id': 'LUK', 'en_name': 'Luke'},
    '44': {'id': 'JHN', 'en_name': 'John'},
    '45': {'id': 'ACT', 'en_name': 'Acts'},
    '46': {'id': 'ROM', 'en_name': 'Romans'},
    '47': {'id': '1CO', 'en_name': '1 Corinthians'},
    '48': {'id': '2CO', 'en_name': '2 Corinthians'},
    '49': {'id': 'GAL', 'en_name': 'Galatians'},
    '50': {'id': 'EPH', 'en_name': 'Ephesians'},
    '51': {'id': 'PHP', 'en_name': 'Philippians'},
    '52': {'id': 'COL', 'en_name': 'Colossians'},
    '53': {'id': '1TH', 'en_name': '1 Thessalonians'},
    '54': {'id': '2TH', 'en_name': '2 Thessalonians'},
    '55': {'id': '1TI', 'en_name': '1 Timothy'},
    '56': {'id': '2TI', 'en_name': '2 Timothy'},
    '57': {'id': 'TIT', 'en_name': 'Titus'},
    '58': {'id': 'PHM', 'en_name': 'Philemon'},
    '59': {'id': 'HEB', 'en_name': 'Hebrews'},
    '60': {'id': 'JAS', 'en_name': 'James'},
    '61': {'id': '1PE', 'en_name': '1 Peter'},
    '62': {'id': '2PE', 'en_name': '2 Peter'},
    '63': {'id': '1JN', 'en_name': '1 John'},
    '64': {'id': '2JN', 'en_name': '2 John'},
    '65': {'id': '3JN', 'en_name': '3 John'},
    '66': {'id': 'JUD', 'en_name': 'Jude'},
    '67': {'id': 'REV', 'en_name': 'Revelation'},
    '68': {'id': 'TOB', 'en_name': 'Tobit'},
    '69': {'id': 'JDT', 'en_name': 'Judith'},
    '70': {'id': 'ESG', 'en_name': 'Esther Greek'},
    '71': {'id': 'WIS', 'en_name': 'Wisdom of Solomon'},
    '72': {'id': 'SIR', 'en_name': 'Sirach'},
    '73': {'id': 'BAR', 'en_name': 'Baruch'},
    '74': {'id': 'LJE', 'en_name': 'Letter of Jeremiah'},
    '75': {'id': 'S3Y', 'en_name': 'Song of the 3 Young Men'},
    '76': {'id': 'SUS', 'en_name': 'Susanna'},
    '77': {'id': 'BEL', 'en_name': 'Bel and the Dragon'},
    '78': {'id': '1MA', 'en_name': '1 Maccabees'},
    '79': {'id': '2MA', 'en_name': '2 Maccabees'},
    '80': {'id': '3MA', 'en_name': '3 Maccabees'},
    '81': {'id': '4MA', 'en_name': '4 Maccabees'},
    '82': {'id': '1ES', 'en_name': '1 Esdras (Greek)'},
    '83': {'id': '2ES', 'en_name': '2 Esdras (Latin)'},
    '84': {'id': 'MAN', 'en_name': 'Prayer of Manasseh'},
    '85': {'id': 'PS2', 'en_name': 'Psalm 151'},
    '86': {'id': 'ODA', 'en_name': 'Odae/Odes'},
    '87': {'id': 'PSS', 'en_name': 'Psalms of Solomon'},
    'A4': {'id': 'EZA', 'en_name': 'Ezra Apocalypse'},
    'A5': {'id': '5EZ', 'en_name': '5 Ezra'},
    'A6': {'id': '6EZ', 'en_name': '6 Ezra'},
    'B2': {'id': 'DAG', 'en_name': 'Daniel Greek'},
    'B3': {'id': 'PS3', 'en_name': 'Psalms 152-155'},
    'B4': {'id': '2BA', 'en_name': '2 Baruch (Apocalypse)'},
    'B5': {'id': 'LBA', 'en_name': 'Letter of Baruch'},
    'B6': {'id': 'JUB', 'en_name': 'Jubilees'},
    'B7': {'id': 'ENO', 'en_name': 'Enoch'},
    'B8': {'id': '1MQ', 'en_name': '1 Meqabyan/Mekabis'},
    'B9': {'id': '2MQ', 'en_name': '2 Meqabyan/Mekabis'},
    'C0': {'id': '3MQ', 'en_name': '3 Meqabyan/Mekabis'},
    'C1': {'id': 'REP', 'en_name': 'Reproof'},
    'C2': {'id': '4BA', 'en_name': '4 Baruch'},
    'C3': {'id': 'LAO', 'en_name': 'Letter to the Laodiceans'},
    'A0': {'id': 'FRT', 'en_name': 'Front Matter'},
    'A1': {'id': 'BAK', 'en_name': 'Back Matter'},
    'A2': {'id': 'OTH', 'en_name': 'Other Matter'},
    'A7': {'id': 'INT', 'en_name': 'Introduction Matter'},
    'A8': {'id': 'CNC', 'en_name': 'Concordance'},
    'A9': {'id': 'GLO', 'en_name': 'Glossary / Wordlist'},
    'B0': {'id': 'TDX', 'en_name': 'Topical Index'},
    'B1': {'id': 'NDX', 'en_name': 'Names Index'}
}

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