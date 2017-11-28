#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This tool reads USFM files generated by csvtousfm3.py
and injects tW links into the matching Greek or Hebrew words.

Errors are recorded in errors.log in the output directory.

Assumptions:
1. The tW RC contains a list of occurrences for each word.
2. This list of occurrences is stored in the config.yaml file.
3. The word content contains a #2 heading titled "Word Data" under which are strong's numbers.
"""

import argparse
import os
import sys
import re
import logging

from resource_container import factory, ResourceContainer
from libraries.tools.file_utils import write_file, read_file

LOGGER_NAME='map_tw_to_usfm'

class USFMWordReader:
    """
    A utility for reading words from a USFM file and writing changes to
    the words
    """
    def __init__(self, usfm):
        self.lines = usfm.splitlines()
        self.line = ''
        self.book = None
        self.chapter = None
        self.verse = None
        self.header = []
        self.read_lines = []

        # locate book id
        while not self.book and not self.line.startswith('\\c ') and self.lines:
            self.line = self.lines.pop(0)
            self.header.append(self.line)
            if self.line.startswith('\\id'):
                # get id
                match = re.findall('^\\\id\s+(\w+)\s+.*', self.line, re.IGNORECASE | re.UNICODE)
                if match:
                    self.book = match[0].lower()
                else:
                    raise Exception('Malformed USFM. Unable to parse book id: {}'.format(self.line))

        if not self.book:
            raise Exception('Malformed USFM. Could not find book id.')

    def __str__(self):
        return '\n'.join(self.header + self.read_lines + self.lines)

    def __iter__(self):
        return self

    # Python 3
    def __next__(self):
        return self.findNextWord()

    # Python 2
    def next(self):
        return self.findNextWord()

    def amendLine(self, newLine):
        """
        Amends the line that was last read
        :param newLine:
        :return:
        """
        self.read_lines[-1] = newLine

    def location(self):
        """
        Returns the location of the current line
        :return:
        """
        return self.book, self.chapter, self.verse

    def findNextWord(self):
        """
        Returns the next word in the USFM.
        :return: line, strong
        """
        self.line = ''
        while (not self.line or not self.line.startswith('\\w ')) and self.lines:
            strong = None
            self.line = self.lines.pop(0)
            self.read_lines.append(self.line)

            # start chapter
            if re.match(r'\\c\b', self.line):
                match = re.findall(r'^\\c\s+(\d+)', self.line, re.IGNORECASE | re.UNICODE)
                if match:
                    self.chapter = _unzpad(match[0])
                    self.verse = None
                else:
                    raise Exception('Malformed USFM. Unable to parse chapter number: {}'.format(self.line))

            # start verse
            if re.match(r'\\v\b', self.line):
                match = re.findall(r'^\\v\s+(\d+)', self.line, re.IGNORECASE | re.UNICODE)
                if match:
                    self.verse = _unzpad(match[0])
                else:
                    raise Exception('Malformed USFM. Unable to parse verse number: {}'.format(self.line))

            # start original language word
            if re.match(r'\\w\b', self.line):
                match = re.findall(r'strong="([\w]+)"', self.line, re.IGNORECASE | re.UNICODE)
                if match:
                    strong = match[0]
                else:
                    raise Exception('Malformed USFM. Unable to parse strong number: {}'.format(self.line))

            # validate
            if self.chapter and self.verse and strong:
                return self.line, strong
            elif self.line.startswith('\\w'):
                raise Exception('Malformed USFM. USFM tags appear to be out of order.')

        raise StopIteration


def indexWordsLocation(words_rc):
    """
    Generates an index of word occurrences where words may be looked up by
    textual occurrence.
    :param words_rc:
    :type words_rc: ResourceContainer.RC
    :return: a dictionary of words keyed by location
    """
    logger = logging.getLogger(LOGGER_NAME)
    config = words_rc.config()
    location_categories = ['occurrences', 'false_positives']
    index = {name:{} for name in location_categories}
    for word in config:
        word_obj = config[word]
        for location_category in word_obj:
            if location_category in location_categories:
                locations = word_obj[location_category]
                for location in locations:
                    try:
                        parts = location.split('/')
                        length = len(parts)
                        verse = _unzpad(parts[length-1])
                        chapter = _unzpad(parts[length-2])
                        book = parts[length - 3]
                        path = '{}/{}/{}'.format(book, chapter, verse)
                        if path in index[location_category]:
                            # append to index
                            index[location_category][path].append(word)
                        else:
                            # create index
                            index[location_category][path] = [word]
                    except Exception as e:
                        logger.error('Failed to parse location: {}'.format(location))
                        raise e
    return index

def _unzpad(strint):
    """
    Removes zpadding from an integer string
    :param strint: a string that contains an integer value
    :return:
    """
    return '{}'.format(int(strint))

def findStrongs(word, words_rc):
    """
    Retrieves the strong numbers for a word from it's data file
    :param word: the word to index
    :param words_rc:
    :type words_rc: ResourceContainer.RC
    :return: a list of strongs
    """

    # TRICKY: the config.yaml does not provide sufficient information to
    # locate the word, however we only have 3 options.
    # There should not be any duplicates within these folders.
    logger = logging.getLogger(LOGGER_NAME)

    numbers = []
    data = words_rc.read_chunk('kt', word)
    if not data:
        data = words_rc.read_chunk('names', word)
    if not data:
        data = words_rc.read_chunk('other', word)
    if not data:
        # TRICKY: ignore missing words. The config.yaml file was inaccurate
        return numbers

    try:
        numbers = parseStrongs(data)
    except Exception as e:
        category = _getWordCategory(word, words_rc)
        logger.error('{} in word "{}/{}"'.format(e, category, word))

    return numbers

def parseStrongs(word_data):
    """
    Parses the strong's numbers from word data
    :param word_data:
    :return:
    """
    header = re.findall('^#+\s*Word\s+Data\s*\:?.*', word_data, re.MULTILINE | re.IGNORECASE)
    if header:
        word_data = word_data.split(header[0])[1]
        return re.findall('[HG]\d+', word_data, re.MULTILINE | re.IGNORECASE)
    else:
        raise Exception('Missing Word Data section')

def _getWordCategory(word, words_rc):
    """
    Retrieves the category of a word
    :param word:
    :param words_rc:
    :type words_rc: ResourceContainer.RC
    :return:
    """
    # TRICKY: the config.yaml does not provide enough information for us to backtrack words.
    # however, we know there are only 3 locations
    categories = ['kt', 'names', 'other']
    for cat in categories:
        if '{}.md'.format(word) in words_rc.chunks(cat):
            return cat
    return None

def _makeWordLink(word, words_rc):
    """
    Generates a language agnostic link to a tW
    :param word:
    :param words_rc:
    :type words_rc: ResourceContainer.RC
    :return: a new rc link
    """
    category = _getWordCategory(word, words_rc)
    if not category:
        raise Exception('Failed to look up category for word {}'.format(word))

    return 'rc://*/tw/dict/bible/{}/{}'.format(category, word)

def _getLocationWords(location, words_index):
    """
    Retrieves the words found at the passage location
    :param location: The passage location e.g. book/chapter/verse without z-padding
    :param words_index:
    :return: a list of words
    """
    if location in words_index:
        return words_index[location]
    else:
        return []

def _getWords(strongs, words_strongs_index):
    """
    Returns a list of words that match the strong's number.
    :param strongs:
    :param words_strongs_index:
    :param words_false_positives_index:
    :return:
    """
    if strongs in words_strongs_index:
        return words_strongs_index[strongs]
    else:
        return []

def indexWordByStrongs(words_rc):
    """
    Generates an index of words keyed by strong numbers
    :param words_rc:
    :type words_rc: ResourceContainer.RC
    :return: a dictionary of words keyed by strong's
    """
    logger = logging.getLogger(LOGGER_NAME)
    index = {}
    for category in words_rc.chapters():
        for word in words_rc.chunks(category):
            word = os.path.splitext(word)[0]
            data = words_rc.read_chunk(category, word)
            numbers = []
            try:
                numbers = parseStrongs(data)
            except Exception as e:
                logger.error('{} in word "{}/{}"'.format(e, category, word))
            for num in numbers:
                if num in index:
                    # append word to strong
                    index[num].append(word)
                else:
                    # create index
                    index[num] = [word]
    return index

def indexLocationStrongs(location, words_index, words_rc, strongs_index=None):
    """
    Generates an index of strong numbers associated with words found in the given location.
    If the existing index is provided this may not hit the filesystem.
    :param location:
    :param words_index:
    :param words_rc:
    :param strongs_index: the existing index. This will be updated if set
    :return: a dictionary of strong numbers keyed by word
    """
    words = _getLocationWords(location, words_index)
    if strongs_index:
        index = strongs_index
    else:
        index = {}

    for word in words:
        if word not in index:
            index[word] = findStrongs(word, words_rc)
    return index

def getStrongs(word, strongs_index):
    """
    Retrieves the strongs found for a word
    :param word:
    :param strongs_index:
    :return: a list of strong numbers
    """
    if word in strongs_index:
        return strongs_index[word]
    else:
        return []

def mapWord(strong_number, words, strongs_index):
    """
    Returns a word that is mapped to the strong's number
    :param strong_number:
    :param words: a list of words available for mapping. These are available based on the passage location.
    :param strongs_index: an index of strong's numbers from which to read
    :return: the word or None
    """
    for word in words:
        strongs = getStrongs(word, strongs_index)
        for strong in strongs:
            # TRICKY: reverse zero pad numbers from the index to match the length
            formatted_strong = (strong + '000000')[:len(strong_number)]
            if formatted_strong.lower() == strong_number.lower():
                return word
    return None

def mapUSFMByGlobalSearch(usfm, words_rc, words_strongs_index, words_false_positives_index):
    """
    Injects tW links into un-matched usfm words as matches are found in the global index.
    :param usfm:
    :param words_rc:
    :param words_strongs_index:
    :param words_false_positives_index:
    :return:
    """
    logger = logging.getLogger(LOGGER_NAME)
    reader = USFMWordReader(usfm)
    for line, strong in reader:
        if re.match(r'.*x-tw=', line):
            # skip lines already mapped
            continue

        book, chapter, verse = reader.location()
        location = '{}/{}/{}'.format(book, chapter, verse)
        words = _getWords(strong, words_strongs_index)
        # exclude words marked as false positives
        false_positives = _getLocationWords(location, words_false_positives_index)
        filtered = [w for w in words if not w in false_positives]
        if filtered:
            if len(filtered) == 1:
                # inject link at end
                link = 'x-tw="{}"'.format(_makeWordLink(filtered[0], words_rc))
                reader.amendLine(line.replace('\w*', ' ' + link + ' \w*'))
            else:
                logger.info('Multiple matches found for {}'.format(strong))
    return unicode(reader)

# TRICKY: we purposely make strongs_index a mutable parameter
# this allows us to maintain the strong's index.
def mapUSFMByOccurrence(usfm, words_rc, words_index, strongs_index={}):
    """
    Injects tW links into the usfm as matches are found in the list of occurrences.
    :param usfm:
    :type usfm: basestring
    :param words_rc:
    :type words_rc: ResourceContainer.RC
    :param words_index: the index of words keyed by location.
    :param strongs_index: the index of word strong numbers.
    :return: the newly mapped usfm
    """
    # logger = logging.getLogger(LOGGER_NAME)

    reader = USFMWordReader(usfm)
    for line, strong in reader:
        book, chapter, verse = reader.location()
        location = '{}/{}/{}'.format(book, chapter, verse)
        words = _getLocationWords(location, words_index)
        strongs_index = indexLocationStrongs(location, words_index, words_rc, strongs_index)
        word = mapWord(strong, words, strongs_index)
        if word:
            # inject link at end
            link = 'x-tw="{}"'.format(_makeWordLink(word, words_rc))
            reader.amendLine(line.replace('\w*', ' ' + link + ' \w*'))
        elif words:
            pass
            # logger.warning('No match found for {} at {}'.format(strong, location))
    return unicode(reader)

def mapDir(usfm_dir, words_rc, output_dir):
    """
    Maps tW to words within each USFM file found in the directory.
    :param usfm_dir: a directory containing USFM files generated by `csvtousfm3`
    :param words_rc: the tW resource container
    :type words_rc: ResourceContainer.RC
    :param output_dir: a directory where the newly mapped usfm will be saved
    :return:
    """
    usfm_files = []
    location_index = {}
    strongs_index = {}
    for root, dirs, files in os.walk(usfm_dir):
        usfm_files.extend(files)
        print('Generating occurrences index')
        location_index = indexWordsLocation(words_rc)
        print('Generating strongs index')
        strongs_index = indexWordByStrongs(words_rc)
        break

    for file_name in usfm_files:
        if not file_name.endswith('.usfm'):
            continue

        file = os.path.join(usfm_dir, file_name)
        print('{}'.format(file_name))
        usfm = mapUSFMByOccurrence(read_file(file), words_rc, location_index['occurrences'])
        usfm = mapUSFMByGlobalSearch(usfm, words_rc, strongs_index, location_index['false_positives'])
        outfile = os.path.join(output_dir, os.path.basename(file))
        write_file(outfile, usfm)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-u', '--usfm', dest='usfm', required=True, help='Directory containing USFM files to read')
    parser.add_argument('-w', '--words', dest='words', required=True, help='tW resource container to read. You can download one from https://git.door43.org/Door43/en_tw')
    parser.add_argument('-o', '--output', dest='output', required=True, help='Director to which the updated USFM will be saved')

    args = parser.parse_args(sys.argv[1:])
    if os.path.isfile(args.output):
        raise Exception('Output must be a directory')

    rc = factory.load(args.words)

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

    # start
    mapDir(args.usfm, rc, args.output)

    # announce errors or clean up log file
    if os.path.isfile(errors_log_file):
        statinfo = os.stat(errors_log_file)
        if statinfo.st_size > 0:
            print('WARNING: errors were detected. See {} for details'.format(errors_log_file))
        else:
            os.remove(errors_log_file)

    print('Finished')

