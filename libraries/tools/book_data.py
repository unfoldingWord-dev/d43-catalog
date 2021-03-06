def get_book_by_osis_id(id):
    """
    Retrieves book meta data
    :param id: the osis book id
    :return:
    """
    sort = find_key(id, osis_ids)
    return get_book_by_sort(sort)

def get_book_by_sort(sort):
    """
    Retrieves book metadata
    :param sort: the sort order of the book to look up
    :return:
    """
    if sort in osis_ids and sort in usfm_ids and sort in en_names:
        return {
            'osis_id': osis_ids[sort],
            'usfm_id': usfm_ids[sort],
            'en_name': en_names[sort],
            'sort': sort
        }
    return None

def find_key(value, dict):
    """
    Looks up the key for the case insensitive value
    :param value:
    :return:
    """
    for k, v in dict.iteritems():
        if v.lower() == value.lower():
            return k

osis_ids = {
    # OT
    '01':'Gen',
    '02':'Exod',
    '03':'Lev',
    '04':'Num',
    '05':'Deut',
    '06':'Josh',
    '07':'Judg',
    '08':'Ruth',
    '09':'1Sam',
    '10':'2Sam',
    '11':'1Kgs',
    '12':'2Kgs',
    '13':'1Chr',
    '14':'2Chr',
    '15':'Ezra',
    '16':'Neh',
    '17':'Esth',
    '18':'Job',
    '19':'Ps',
    '20':'Prov',
    '21':'Eccl',
    '22':'Song',
    '23':'Isa',
    '24':'Jer',
    '25':'Lam',
    '26':'Ezek',
    '27':'Dan',
    '28':'Hos',
    '29':'Joel',
    '30':'Amos',
    '31':'Obad',
    '32':'Jonah',
    '33':'Mic',
    '34':'Nah',
    '35':'Hab',
    '36':'Zeph',
    '37':'Hag',
    '38':'Zech',
    '39':'Mal',
    # NT
    '41':'Matt',
    '42':'Mark',
    '43':'Luke',
    '44':'John',
    '45':'Acts',
    '46':'Rom',
    '47':'1Cor',
    '48':'2Cor',
    '49':'Gal',
    '50':'Eph',
    '51':'Phil',
    '52':'Col',
    '53':'1Thess',
    '54':'2Thess',
    '55':'1Tim',
    '56':'2Tim',
    '57':'Titus',
    '58':'Phlm',
    '59':'Heb',
    '60':'Jas',
    '61':'1Pet',
    '62':'2Pet',
    '63':'1John',
    '64':'2John',
    '65':'3John',
    '66':'Jude',
    '67':'Rev'
}

usfm_ids = {
    # OT
    '01': 'GEN',
    '02': 'EXO',
    '03': 'LEV',
    '04': 'NUM',
    '05': 'DEU',
    '06': 'JOS',
    '07': 'JDG',
    '08': 'RUT',
    '09': '1SA',
    '10': '2SA',
    '11': '1KI',
    '12': '2KI',
    '13': '1CH',
    '14': '2CH',
    '15': 'EZR',
    '16': 'NEH',
    '17': 'EST',
    '18': 'JOB',
    '19': 'PSA',
    '20': 'PRO',
    '21': 'ECC',
    '22': 'SNG',
    '23': 'ISA',
    '24': 'JER',
    '25': 'LAM',
    '26': 'EZK',
    '27': 'DAN',
    '28': 'HOS',
    '29': 'JOL',
    '30': 'AMO',
    '31': 'OBA',
    '32': 'JON',
    '33': 'MIC',
    '34': 'NAM',
    '35': 'HAB',
    '36': 'ZEP',
    '37': 'HAG',
    '38': 'ZEC',
    '39': 'MAL',
    # NT
    '41': 'MAT',
    '42': 'MRK',
    '43': 'LUK',
    '44': 'JHN',
    '45': 'ACT',
    '46': 'ROM',
    '47': '1CO',
    '48': '2CO',
    '49': 'GAL',
    '50': 'EPH',
    '51': 'PHP',
    '52': 'COL',
    '53': '1TH',
    '54': '2TH',
    '55': '1TI',
    '56': '2TI',
    '57': 'TIT',
    '58': 'PHM',
    '59': 'HEB',
    '60': 'JAS',
    '61': '1PE',
    '62': '2PE',
    '63': '1JN',
    '64': '2JN',
    '65': '3JN',
    '66': 'JUD',
    '67': 'REV',
    # APO/DEUT
    '68': 'TOB',
    '69': 'JDT',
    '70': 'ESG',
    '71': 'WIS',
    '72': 'SIR',
    '73': 'BAR',
    '74': 'LJE',
    '75': 'S3Y',
    '76': 'SUS',
    '77': 'BEL',
    '78': '1MA',
    '79': '2MA',
    '80': '3MA',
    '81': '4MA',
    '82': '1ES',
    '83': '2ES',
    '84': 'MAN',
    '85': 'PS2',
    '86': 'ODA',
    '87': 'PSS',
    'A4': 'EZA',
    'A5': '5EZ',
    'A6': '6EZ',
    'B2': 'DAG',
    'B3': 'PS3',
    'B4': '2BA',
    'B5': 'LBA',
    'B6': 'JUB',
    'B7': 'ENO',
    'B8': '1MQ',
    'B9': '2MQ',
    'C0': '3MQ',
    'C1': 'REP',
    'C2': '4BA',
    'C3': 'LAO',
    'A0': 'FRT',
    'A1': 'BAK',
    'A2': 'OTH',
    'A7': 'INT',
    'A8': 'CNC',
    'A9': 'GLO',
    'B0': 'TDX',
    'B1': 'NDX'
}

en_names = {
    '01':'Genesis',
    '02':'Exodus',
    '03':'Leviticus',
    '04':'Numbers',
    '05':'Deuteronomy',
    '06':'Joshua',
    '07':'Judges',
    '08':'Ruth',
    '09':'1 Samuel',
    '10':'2 Samuel',
    '11':'1 Kings',
    '12':'2 Kings',
    '13':'1 Chronicles',
    '14':'2 Chronicles',
    '15':'Ezra',
    '16':'Nehemiah',
    '17':'Esther (Hebrew)',
    '18':'Job',
    '19':'Psalms',
    '20':'Proverbs',
    '21':'Ecclesiastes',
    '22':'Song of Songs',
    '23':'Isaiah',
    '24':'Jeremiah',
    '25':'Lamentations',
    '26':'Ezekiel',
    '27':'Daniel (Hebrew)',
    '28':'Hosea',
    '29':'Joel',
    '30':'Amos',
    '31':'Obadiah',
    '32':'Jonah',
    '33':'Micah',
    '34':'Nahum',
    '35':'Habakkuk',
    '36':'Zephaniah',
    '37':'Haggai',
    '38':'Zechariah',
    '39':'Malachi',
    '41':'Matthew',
    '42':'Mark',
    '43':'Luke',
    '44':'John',
    '45':'Acts',
    '46':'Romans',
    '47':'1 Corinthians',
    '48':'2 Corinthians',
    '49':'Galatians',
    '50':'Ephesians',
    '51':'Philippians',
    '52':'Colossians',
    '53':'1 Thessalonians',
    '54':'2 Thessalonians',
    '55':'1 Timothy',
    '56':'2 Timothy',
    '57':'Titus',
    '58':'Philemon',
    '59':'Hebrews',
    '60':'James',
    '61':'1 Peter',
    '62':'2 Peter',
    '63':'1 John',
    '64':'2 John',
    '65':'3 John',
    '66':'Jude',
    '67':'Revelation',
    '68':'Tobit',
    '69':'Judith',
    '70':'Esther Greek',
    '71':'Wisdom of Solomon',
    '72':'Sirach',
    '73':'Baruch',
    '74':'Letter of Jeremiah',
    '75':'Song of the 3 Young Men',
    '76':'Susanna',
    '77':'Bel and the Dragon',
    '78':'1 Maccabees',
    '79':'2 Maccabees',
    '80':'3 Maccabees',
    '81':'4 Maccabees',
    '82':'1 Esdras (Greek)',
    '83':'2 Esdras (Latin)',
    '84':'Prayer of Manasseh',
    '85':'Psalm 151',
    '86':'Odae/Odes',
    '87':'Psalms of Solomon',
    'A4':'Ezra Apocalypse',
    'A5':'5 Ezra',
    'A6':'6 Ezra',
    'B2':'Daniel Greek',
    'B3':'Psalms 152-155',
    'B4':'2 Baruch (Apocalypse)',
    'B5':'Letter of Baruch',
    'B6':'Jubilees',
    'B7':'Enoch',
    'B8':'1 Meqabyan/Mekabis',
    'B9':'2 Meqabyan/Mekabis',
    'C0':'3 Meqabyan/Mekabis',
    'C1':'Reproof',
    'C2':'4 Baruch',
    'C3':'Letter to the Laodiceans',
    'A0':'Front Matter',
    'A1':'Back Matter',
    'A2':'Other Matter',
    'A7':'Introduction Matter',
    'A8':'Concordance',
    'A9':'Glossary / Wordlist',
    'B0':'Topical Index',
    'B1':'Names Index'
}