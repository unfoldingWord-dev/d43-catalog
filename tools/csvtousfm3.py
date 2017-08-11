#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This tool reads a CSV file containing a list of words and converts it into USFM3 with word level attributes.
"""

import argparse
import sys
import csv
from tools.file_utils import write_file

def convert(lang, csv_file):
    """
    Converts a CSV file to USFM3
    :param lang: the language of the words in the CSV file
    :param csv_file: the csv to be converted to USFM
    :return:
    """
    with open(csv_file) as file:
        usfm = []
        csvreader = csv.DictReader(file)
        lastverse = None
        for row in csvreader:
            row_usfm = convert_row(lang, row)
            if not row_usfm: continue

            # insert verse marker
            # TODO: test this comparison
            if not lastverse or row['VERSE'] > lastverse:
                if lastverse:
                    usfm.append('')

                lastverse = row['VERSE']
                # TODO: just get the verse
                usfm.append('\\v {}'.format(lastverse))

            usfm.append(row_usfm)
        return '\n'.join(usfm)

def convert_row(lang, row):
    """
    Converts a single CSV row to USFM3
    :param lang: the language of the word
    :param row: a row from a CSV file
    :return: the generated USFM3
    """
    word, punctuation = split_puncuation(row['UMEDIEVAL'])

    return '\w {}|lemma="{}" strongs="G{}" x-morph="Gr,{}{}{}"\w*{}'.format(
        word,
        row['ULEMMA'],
        row['LEXEME'].zfill(5),
        row['SYN'].replace('.', ','),
        row['MORPH'].replace('.', ','),
        row['LEX'].replace('.', ','),
        punctuation
    )

def split_puncuation(word):
    """
    Separates punctuation from a word
    :param word:
    :return: a tuple containing the cleaned word, and punctuation
    """
    punctuation = ['.', ',']
    if word[-1:] in punctuation:
        return word[:-1], word[-1:]
    else:
        return word, ''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-l', '--lang', dest='lang', required=True, help='The language represented in the CSV file')
    parser.add_argument('-i', '--input', dest='input', required=True, help='CSV file to convert')
    parser.add_argument('-o', '--output', dest='output', required=True, help='Where to save the generated USFM')

    args = parser.parse_args(sys.argv[1:])

    usfm = convert(args['lang'], args['input'])
    write_file(args['output'], usfm)