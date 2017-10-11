# coding=utf-8
import re

def strip_word_data(usfm):
    """
    Removes word data from a usfm string
    :param usfm:
    :return:
    """
    return re.sub(r'\\w\s*([^\\w\|]*)[^\\w]*\\w\*', r'\g<1>', usfm)

def convert_chunk_markers(str):
    """
    Replaces \ts chunk markers to \s5 for backwards compatibility
    :param str:
    :return: the converted string
    """
    return re.sub(r'\\ts\b', '\\s5', str)