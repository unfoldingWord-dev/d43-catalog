# -*- coding: utf-8 -*-

#
# These are utilities specifically designed for the ts v2 catalog handler.
#

import re
import codecs

import dateutil.parser
import os
import json
import tempfile
import shutil
import pytz

from libraries.lambda_handlers.handler import Handler
from libraries.tools.file_utils import read_file, write_file
from libraries.tools.url_utils import get_url
from usfm_tools.transform import UsfmTransform
from libraries.tools.usfm_utils import usfm3_to_usfm2
from libraries.tools.versification import hebrew_to_ufw


def download_chunks(pid, dest):
    """
    Downloads the chunks for the bible book
    :param pid:
    :return: the chunk json data or None
    """
    try:
        data = get_url('https://cdn.door43.org/bible/txt/1/{}/chunks.json'.format(pid))
        return json.loads(data)
    except:
        return None


def index_chunks(chunks):
    """
    Turns a chunks array into a dictionary keyed by chapter
    :param chunks:
    :return:
    """
    dict = {}
    for chunk in chunks:
        if not chunk['chp'] in dict:
            dict[chunk['chp']] = []
        dict[chunk['chp']].append(chunk['firstvs'])
    return dict


def tn_tsv_to_json(tsv, chunks):
    """
    Converts a tsv dictionary to a json object
    :param tsv: a tsv dictionary
    :param chunks: a dictionary of chunk data used to group notes
    :return: a json object
    """
    current_chapter = None
    current_chunk_verse = None
    current_chunk = None
    json = []
    for row in tsv:
        try:
            chapter = int(row['Chapter'])
            verse = int(row['Verse'])
        except ValueError:
            # collect book and chapter intro notes
            if current_chunk is not None:
                json.append(current_chunk)
                current_chunk = None

            chapter = row['Chapter']
            verse = row['Verse']

            if verse == 'intro':
                verse = 'title'  # TRICKY: tS uses 'title' instead of intro
            else:
                # whatever the verse is it's not supported
                continue

            if isinstance(chapter, int):
                chapter = int(chapter)
            if chapter == 'front':
                pass
            else:
                try:
                    chapter = int(chapter)
                    chapter = pad_to_match(chapter, chunks)
                    if chapter not in chunks:
                        raise Exception('Missing chapter "{}" key in chunk json'.format(chapter))
                except ValueError:
                    # whatever the chapter is it's not supported
                    continue

            if row['GLQuote']:
                ref = row['GLQuote']
            else:
                ref = 'General Information'

            json.append({
                'id': '{}-{}'.format(chapter, verse),
                'tn': [{
                    'ref': ref,
                    'text': row['OccurrenceNote']
                }]
            })
            continue

        # zero pad numbers to match chunk scheme
        chapter = pad_to_match(chapter, chunks)
        if chapter not in chunks:
            raise Exception('Missing chapter "{}" key in chunk json'.format(chapter))

        verse = pad_to_match(verse, chunks[chapter])

        # prepare next note chunk
        verse_starts_chunk = verse in chunks[chapter]
        chunk_is_finished = current_chunk_verse != verse
        if current_chapter != chapter or (chunk_is_finished and verse_starts_chunk):
            current_chapter = chapter
            current_chunk_verse = verse
            if current_chunk is not None:
                json.append(current_chunk)
            current_chunk = {
                'id': '{}-{}'.format(chapter, current_chunk_verse),
                'tn': []
            }

        # collect notes
        current_chunk['tn'].append({
            'ref': row['GLQuote'],
            'text': row['OccurrenceNote']
        })

    # close last chunk
    if current_chunk is not None:
        json.append(current_chunk)

    return json


def pad_to_match(num, matches, max_len=3):
    """
    z-fills a number until a match has been found.
    :param num: the number to zfill
    :param matches: the available matches
    :param max_len: the maximum length to zfill
    :return: the z-filled number if a match was found otherwise the original value
    """
    padded_num = '{}'.format(num)
    while len(padded_num) < max_len and padded_num not in matches:
        padded_num = padded_num.zfill(len(padded_num) + 1)
        if padded_num in matches:
            return padded_num
    return '{}'.format(num)


def prep_data_upload(key, data, temp_dir):
    """
    Prepares some data for upload to s3
    :param key:
    :param data:
    :param temp_dir
    :return:
    """
    temp_file = os.path.join(temp_dir, key)
    write_file(temp_file, json.dumps(data, sort_keys=True))
    return {
        'key': key,
        'path': temp_file
    }


def build_usx(usfm_dir, usx_dir):
    """
    Builds the usx from usfm after performing some custom processing
    :param usfm_dir:
    :param usx_dir:
    :return:
    """
    # strip word data
    files = os.listdir(usfm_dir)
    usfm2_dir = tempfile.mkdtemp(prefix='usfm2')
    try:
        for name in files:
            if name == '.DS_Store':
                continue
            f = os.path.join(usfm_dir, name)
            usfm3 = read_file(f)
            usfm2 = usfm3_to_usfm2(usfm3)
            out_f = os.path.join(usfm2_dir, name)
            write_file(out_f, usfm2)

        UsfmTransform.buildUSX(usfm2_dir, usx_dir, '', True)
    finally:
        try:
            shutil.rmtree(usfm2_dir)
        finally:
            pass


def get_rc_type(rc_format):
    """
    Returns the first resource type found in an array of formats
    :param rc_format:
    :return:
    """
    re_type = re.compile(r'type=(\w+)', re.UNICODE | re.IGNORECASE)
    if 'conformsto=rc0.2' in rc_format['format'] and 'type' in rc_format['format']:
        match = re_type.search(rc_format['format'])
        return match.group(1)
    return None


def max_modified_date(obj, modified):
    """
    Return the largest modified date
    If the object does not have a date_modified the argument is returned
    :param obj:
    :param modified:
    :return:
    """
    if 'date_modified' not in obj or int(obj['date_modified']) < int(modified):
        return modified
    else:
        return obj['date_modified']


def get_project_from_manifest(manifest, pid):
    """
    Returns the project entry from the manifest
    :param manifest:
    :param pid:
    :return:
    """
    if 'projects' not in manifest:
        return None
    for project in manifest['projects']:
        if project['identifier'] == pid:
            return project
    return None


def max_long_modified_date(obj, modified):
    """
    Return the largest modified date
    If the object does not have a date_modified the argument is returned
    :param obj:
    :param modified:
    :return:
    """
    if 'long_date_modified' not in obj:
        return modified
    elif date_is_older(obj['long_date_modified'], modified):
        return modified
    else:
        return obj['long_date_modified']

def make_legacy_date(date_str):
    """
    Converts a date from the UTC format (used in api v3) to the form in api v2.
    :param date_str:
    :return:
    """
    date_obj = dateutil.parser.parse(date_str)
    try:
        return date_obj.strftime('%Y%m%d')
    except:
        return None


def date_is_older(date_str1, date_str2):
    """
    Checks to see if the first date is older than the second date.
    :param date_str1:
    :param date_str2:
    :return:
    """
    date1 = dateutil.parser.parse(date_str1)
    date2 = dateutil.parser.parse(date_str2)

    # set or normalize the timezone
    target_tz = pytz.timezone('UTC')
    if date1.tzinfo is None:
        date1 = target_tz.localize(date1)
    else:
        date1 = target_tz.normalize(date1)
    if date2.tzinfo is None:
        date2 = target_tz.localize(date2)
    else:
        date2 = target_tz.normalize(date2)
    return date1 < date2

def usx_to_chunked_json(usx, chunks, lid, pid):
    """
    Iterates through the usx and splits it into chunks.
    :param pid:
    :param lid:
    :param chunks:
    :param usx:
    """
    chapter_title_re = re.compile(r'<para\s+style="cl">([^<]+)</para>', re.UNICODE)
    verse_re = re.compile(r'<verse number="([0-9]*)', re.UNICODE)
    chunk_marker = '<note caller="u" style="s5"></note>'
    chapters = []

    chapter_buffer = {}
    chunk_buffer = []
    chapter_index = 0
    effective_chapter = 0
    effective_chapter_title = ''
    effective_verse = 0
    first_effective_verse = effective_verse
    previous_effective_chapter = effective_chapter

    for line in usx:
        # hang on to the current effective chapter and verse throughout the loop
        previous_effective_chapter = effective_chapter
        previous_effective_verse = effective_verse

        if chunk_marker in line:
            # remove chunk marker
            line = line.replace(chunk_marker, '')

        if line == '\n':
            continue

        # detect the translated chapter title
        chapter_title_match = chapter_title_re.search(line)
        if chapter_title_match and effective_chapter > 0:  # TRICKY: don't grab the book title before the first chapter
            effective_chapter_title = chapter_title_match.group(1)
            line = re.sub(chapter_title_re, '', line)

        # detect the start of a new chapter
        if 'chapter number' in line:
            chapter_index += 1
            verse_index = 1
            effective_chapter = chapter_index
            effective_verse = verse_index
            if lid == 'hbo':
                ref = hebrew_to_ufw(b=pid.lower(), c=chapter_index, v=verse_index)
                effective_chapter = ref.c
                effective_verse = ref.v
            line = re.sub(r'<chapter number="\d+" style="c" />\n*', '', line)

        # detect the start of a new verse
        if 'verse number' in line:
            verse_index = int(verse_re.search(line).group(1))
            effective_verse = verse_index
            if lid == 'hbo':
                ref = hebrew_to_ufw(b=pid.lower(), c=chapter_index, v=verse_index)
                effective_chapter = ref.c
                effective_verse = ref.v
            if first_effective_verse == 0:
                first_effective_verse = effective_verse

        if effective_chapter == 0 or effective_verse == 0:
            continue

        chunk_chapter = pad_to_match(effective_chapter, chunks)
        if chunk_chapter not in chunks:
            raise Exception(u'Missing chapter {} in {} {} chunk json'.format(chunk_chapter, lid, pid))
        chunk_verse = pad_to_match(effective_verse, chunks[chunk_chapter])

        chunk_changed = chunk_verse in chunks[chunk_chapter] and effective_verse > 1 and effective_verse != previous_effective_verse
        chapter_changed = chapter_buffer and effective_chapter != previous_effective_chapter

        # close chunk
        if chunk_changed or chapter_changed:
            if chunk_buffer:
                chunk_text = '\n'.join(chunk_buffer)
                chunk_id = '{0}-{1}'.format(str(previous_effective_chapter).zfill(2), str(first_effective_verse).zfill(2))
                chapter_buffer['frames'].append({
                    'id': chunk_id,
                    'img': '',
                    'format': 'usx',
                    'text': chunk_text.strip(),
                    'lastvs': str(previous_effective_verse)
                })
            first_effective_verse = effective_verse
            chunk_buffer = []

        # close chapter
        if chapter_changed:
            chapter_buffer['title'] = effective_chapter_title
            chapters.append(chapter_buffer)
            effective_chapter_title = ''

        # open new chapter
        if effective_chapter != previous_effective_chapter:
            chapter_buffer = {
                'number': str(effective_chapter).zfill(2),
                'ref': '',
                'title': '',
                'frames': []
            }

        # add the line if it's not empty
        if line:
            chunk_buffer.append(line.strip())

    # close last chunk
    if chunk_buffer:
        chunk_text = '\n'.join(chunk_buffer)
        chunk_id = '{0}-{1}'.format(str(previous_effective_chapter).zfill(2), str(first_effective_verse).zfill(2))
        chapter_buffer['frames'].append({
            'id': chunk_id,
            'img': '',
            'format': 'usx',
            'text': chunk_text.strip(),
            'lastvs': str(effective_verse)  # TRICKY: because `previous_effective_verse` is not set for the last chunk
        })

    # close chapter
    chapter_buffer['title'] = effective_chapter_title
    chapters.append(chapter_buffer)

    return chapters


def usx_to_json(usx, path='', reporter=None):
    """
    Iterates through the usx and splits it into frames based on the
    s5 markers.
    This is deprecated.
    :param usx:
    :param path: The path from which the usx is converted. This gives context to error messages
    :param reporter: A lambda handler instance for reporting errors
    :type reporter: Handler
    """
    verse_re = re.compile(r'<verse number="([0-9]*)', re.UNICODE)
    chunk_marker = '<note caller="u" style="s5"></note>'
    chapters = []
    chp = ''
    fr_id = 0
    chp_num = 0
    fr_list = []
    current_vs = -1
    for line in usx:
        if line.startswith('\n'):
            continue

        if "verse number" in line:
            current_vs = verse_re.search(line).group(1)

        if 'chapter number' in line:
            if chp:
                if fr_list:
                    fr_text = '\n'.join(fr_list)
                    try:
                        matches = verse_re.search(fr_text)
                        if matches:
                            first_vs = matches.group(1)
                        else:
                            if reporter:
                                reporter.report_error(u'failed to search for verse in string "{}" ({})'.format(fr_text, path))
                            continue
                    except AttributeError:
                        if reporter:
                            reporter.report_error(u'Unable to parse verses from chunk {}: {} ({})'.format(chp_num, fr_text, path))
                        continue
                    chp['frames'].append({'id': '{0}-{1}'.format(
                        str(chp_num).zfill(2), first_vs.zfill(2)),
                        'img': '',
                        'format': 'usx',
                        'text': fr_text,
                        'lastvs': current_vs
                    })
                chapters.append(chp)
            chp_num += 1
            chp = {'number': str(chp_num).zfill(2),
                   'ref': '',
                   'title': '',
                   'frames': []
                   }
            fr_list = []
            continue

        if chunk_marker in line:
            if chp_num == 0:
                continue

            # is there something else on the line with it? (probably an end-of-paragraph marker)
            if len(line.strip()) > len(chunk_marker):
                # get the text following the chunk marker
                rest_of_line = line.replace(chunk_marker, '')

                # append the text to the previous line, removing the unnecessary \n
                fr_list[-1] = fr_list[-1][:-1] + rest_of_line

            if fr_list:
                fr_text = '\n'.join(fr_list)
                try:
                    first_vs = verse_re.search(fr_text).group(1)
                except AttributeError:
                    if reporter:
                        reporter.report_error(u'Unable to parse verses from chunk {}: {} ({})'.format(chp_num, fr_text, path))
                    continue

                chp['frames'].append({'id': '{0}-{1}'.format(
                    str(chp_num).zfill(2), first_vs.zfill(2)),
                    'img': '',
                    'format': 'usx',
                    'text': fr_text,
                    'lastvs': current_vs
                })
                fr_list = []

            continue

        fr_list.append(line)

    # Append the last frame and the last chapter
    if fr_list:
        fr_text = '\n'.join(fr_list)
        try:
            first_vs = verse_re.search(fr_text).group(1)
            chp['frames'].append({
                'id': '{0}-{1}'.format(str(chp_num).zfill(2), first_vs.zfill(2)),
                'img': '',
                'format': 'usx',
                'text': '\n'.join(fr_list),
                'lastvs': current_vs
            })
        except AttributeError:
            if reporter:
                reporter.report_error(
                    u'Unable to parse verses from chunk {}: {} ({})'.format(chp_num, fr_text, path))

    chapters.append(chp)
    return chapters


def build_json_source_from_usx(path, lid, pid, date_modified, reporter=None):
    """
    Builds a json source object from a USX file
    :param path:
    :param date_modified:
    :param reporter: a lambda handler instance for reporting
    :type reporter: Handler
    :return:
    """
    # use utf-8-sig to remove the byte order mark
    with codecs.open(path, 'r', encoding='utf-8-sig') as in_file:
        usx = in_file.readlines()

    try:
        data = get_url('https://cdn.door43.org/bible/txt/1/{}/chunks.json'.format(pid))
        chunks = index_chunks(json.loads(data))
    except:
        raise 'Failed to retrieve chunk information for {}'.format(path)

    book = usx_to_chunked_json(usx, chunks, lid, pid)

    return {
        'source': {
            'chapters': book,
            'date_modified': date_modified.replace('-', '').split('T')[0]
        }
    }


def convert_rc_links(content, logger=None):
    """
    Converts rc links in the content to legacy links
    :param content:
    :param logger:
    :return:
    """
    rc_titled_link_re = re.compile('\[[^\[\]]+\]\((rc\:\/\/([^\(\)]+))\)')
    rc_link_re = re.compile('\[\[(rc\:\/\/([^\[\]]+))\]\]')

    # find links
    titled_links = rc_titled_link_re.findall(content)
    if not titled_links:
        titled_links = []
    links = rc_link_re.findall(content)
    if not links:
        links = []
    links = links + titled_links

    # process links
    for link in links:
        components = link[1].split('/')
        if len(components) < 4:
            if logger:
                logger.warning(u'Invalid link "{}"'.format(link[1]))
            continue
        lid = components[0]
        rid = components[1]
        # rtype = components[2]
        pid = components[3].replace('-', '_')

        new_link = link[0]
        if rid == 'ta':
            if len(components) < 5:
                if logger:
                    logger.warning(u'Invalid link "{}"'.format(link[1]))
                continue

            module = components[4].replace('-', '_')
            vol = get_legacy_ta_volume(module)
            if not vol:
                # TRICKY: new modules added since the legacy ta won't have a volume in the map
                if logger:
                    logger.warning(
                        'volume not found for {} while parsing link {}. Defaulting to vol1'.format(module, link[0]))
                vol = 'vol1'
            new_link = ':{}:{}:{}:{}:{}'.format(lid, rid, vol, pid, module)
        if rid == 'ulb':
            pass
        if rid == 'udb':
            pass
        if rid == 'obs':
            pass

        content = content.replace(link[0], new_link)
    return content


def get_legacy_ta_volume(module):
    """
    Returns legacy volume of a module.
    If no matching volume is found None will be returned.
    :param module: the slug of the tA module
    :type module: String
    :return: the volume slug or None
    """
    if module in legacy_ta_volume_map:
        return legacy_ta_volume_map[module]
    else:
        return None


legacy_ta_volume_map = {
    "acceptable": "vol1",
    "accuracy_check": "vol1",
    "accurate": "vol1",
    "authority_level1": "vol1",
    "authority_level2": "vol1",
    "authority_level3": "vol1",
    "authority_process": "vol1",
    "church_leader_check": "vol1",
    "clear": "vol1",
    "community_evaluation": "vol1",
    "complete": "vol1",
    "goal_checking": "vol1",
    "good": "vol1",
    "important_term_check": "vol1",
    "intro_check": "vol1",
    "intro_checking": "vol1",
    "intro_levels": "vol1",
    "language_community_check": "vol1",
    "level1": "vol1",
    "level1_affirm": "vol1",
    "level2": "vol1",
    "level3": "vol1",
    "level3_approval": "vol1",
    "level3_questions": "vol1",
    "natural": "vol1",
    "other_methods": "vol1",
    "peer_check": "vol1",
    "self_assessment": "vol1",
    "self_check": "vol1",
    "finding_answers": "vol1",
    "gl_strategy": "vol1",
    "open_license": "vol1",
    "statement_of_faith": "vol1",
    "ta_intro": "vol1",
    "translation_guidelines": "vol1",
    "uw_intro": "vol1",
    "door43_translation": "vol1",
    "getting_started": "vol1",
    "intro_publishing": "vol1",
    "intro_share": "vol1",
    "platforms": "vol1",
    "prechecking_training": "vol1",
    "pretranslation_training": "vol1",
    "process_manual": "vol1",
    "publishing_prereqs": "vol1",
    "publishing_process": "vol1",
    "required_checking": "vol1",
    "setup_door43": "vol1",
    "setup_team": "vol1",
    "setup_tsandroid": "vol1",
    "setup_tsdesktop": "vol1",
    "setup_word": "vol1",
    "share_published": "vol1",
    "share_unpublished": "vol1",
    "tsandroid_translation": "vol1",
    "tsdesktop_translation": "vol1",
    "upload_merge": "vol1",
    "word_translation": "vol1",
    "tk_create": "vol1",
    "tk_enable": "vol1",
    "tk_find": "vol1",
    "tk_install": "vol1",
    "tk_intro": "vol1",
    "tk_start": "vol1",
    "tk_update": "vol1",
    "tk_use": "vol1",
    "translate_helpts": "vol1",
    "ts_create": "vol1",
    "ts_first": "vol1",
    "ts_install": "vol1",
    "ts_intro": "vol1",
    "ts_markverses": "vol1",
    "ts_navigate": "vol1",
    "ts_open": "vol1",
    "ts_problem": "vol1",
    "ts_publish": "vol1",
    "ts_request": "vol1",
    "ts_resources": "vol1",
    "ts_select": "vol1",
    "ts_settings": "vol1",
    "ts_share": "vol1",
    "ts_translate": "vol1",
    "ts_update": "vol1",
    "ts_upload": "vol1",
    "ts_useresources": "vol1",
    "uw_app": "vol1",
    "uw_audio": "vol1",
    "uw_checking": "vol1",
    "uw_first": "vol1",
    "uw_install": "vol1",
    "uw_language": "vol1",
    "uw_select": "vol1",
    "uw_update_content": "vol1",
    "choose_team": "vol1",
    "figs_events": "vol1",
    "figs_explicit": "vol1",
    "figs_explicitinfo": "vol1",
    "figs_hypo": "vol1",
    "figs_idiom": "vol1",
    "figs_intro": "vol1",
    "figs_irony": "vol1",
    "figs_metaphor": "vol1",
    "figs_order": "vol1",
    "figs_parables": "vol1",
    "figs_rquestion": "vol1",
    "figs_simile": "vol1",
    "figs_you": "vol1",
    "figs_youdual": "vol1",
    "figs_yousingular": "vol1",
    "file_formats": "vol1",
    "first_draft": "vol1",
    "guidelines_accurate": "vol1",
    "guidelines_church_approved": "vol1",
    "guidelines_clear": "vol1",
    "guidelines_intro": "vol1",
    "guidelines_natural": "vol1",
    "mast": "vol1",
    "qualifications": "vol1",
    "resources_intro": "vol1",
    "resources_links": "vol1",
    "resources_porp": "vol1",
    "resources_types": "vol1",
    "resources_words": "vol1",
    "translate_alphabet": "vol1",
    "translate_discover": "vol1",
    "translate_dynamic": "vol1",
    "translate_fandm": "vol1",
    "translate_form": "vol1",
    "translate_help": "vol1",
    "translate_levels": "vol1",
    "translate_literal": "vol1",
    "translate_manual": "vol1",
    "translate_names": "vol1",
    "translate_problem": "vol1",
    "translate_process": "vol1",
    "translate_retell": "vol1",
    "translate_source_licensing": "vol1",
    "translate_source_text": "vol1",
    "translate_source_version": "vol1",
    "translate_terms": "vol1",
    "translate_tform": "vol1",
    "translate_transliterate": "vol1",
    "translate_unknown": "vol1",
    "translate_wforw": "vol1",
    "translate_whatis": "vol1",
    "translate_why": "vol1",
    "translation_difficulty": "vol1",
    "writing_decisions": "vol1",
    "about_audio_recording": "vol2",
    "approach_to_audio": "vol2",
    "audio_acoustic_principles": "vol2",
    "audio_acoustical_treatments": "vol2",
    "audio_assessing_recording_space": "vol2",
    "audio_best_practices": "vol2",
    "audio_checklist_preparing_project": "vol2",
    "audio_checklist_recording_process": "vol2",
    "audio_checklists": "vol2",
    "audio_creating_new_file": "vol2",
    "audio_digital_recording_devices": "vol2",
    "audio_distribution": "vol2",
    "audio_distribution_amplification_recharging": "vol2",
    "audio_distribution_audio_player": "vol2",
    "audio_distribution_best_solutions": "vol2",
    "audio_distribution_door43": "vol2",
    "audio_distribution_license": "vol2",
    "audio_distribution_local": "vol2",
    "audio_distribution_microsd": "vol2",
    "audio_distribution_mobile_phone": "vol2",
    "audio_distribution_offline": "vol2",
    "audio_distribution_preparing_content": "vol2",
    "audio_distribution_radio": "vol2",
    "audio_distribution_wifi_hotspot": "vol2",
    "audio_editing": "vol2",
    "audio_editing_common_procedures": "vol2",
    "audio_editing_corrections": "vol2",
    "audio_editing_decisions_edit_rerecord": "vol2",
    "audio_editing_decisions_objective_subjective": "vol2",
    "audio_editing_finalizing": "vol2",
    "audio_editing_measuring_selection_length": "vol2",
    "audio_editing_modifying_pauses": "vol2",
    "audio_editing_navigating_timeline": "vol2",
    "audio_editing_using_your_ears": "vol2",
    "audio_equipment_overview": "vol2",
    "audio_equipment_setup": "vol2",
    "audio_field_environment": "vol2",
    "audio_guides": "vol2",
    "audio_guides_conversion_batch": "vol2",
    "audio_guides_normalizing": "vol2",
    "audio_guides_rename_batch": "vol2",
    "audio_interfaces": "vol2",
    "audio_introduction": "vol2",
    "audio_logistics": "vol2",
    "audio_managing_data": "vol2",
    "audio_managing_files": "vol2",
    "audio_managing_folders": "vol2",
    "audio_markers": "vol2",
    "audio_mic_activation": "vol2",
    "audio_mic_fine_tuning": "vol2",
    "audio_mic_gain_level": "vol2",
    "audio_mic_position": "vol2",
    "audio_mic_setup": "vol2",
    "audio_microphone": "vol2",
    "audio_noise_floor": "vol2",
    "audio_optimize_laptop": "vol2",
    "audio_playback_monitoring": "vol2",
    "audio_project_setup": "vol2",
    "audio_publishing_unfoldingword": "vol2",
    "audio_quality_standards": "vol2",
    "audio_recommended_accessories": "vol2",
    "audio_recommended_cables": "vol2",
    "audio_recommended_equipment": "vol2",
    "audio_recommended_headphones": "vol2",
    "audio_recommended_laptops": "vol2",
    "audio_recommended_mic_stands": "vol2",
    "audio_recommended_monitors": "vol2",
    "audio_recommended_playback_equipment": "vol2",
    "audio_recommended_pop_filters": "vol2",
    "audio_recommended_portable_recorders": "vol2",
    "audio_recommended_recording_devices": "vol2",
    "audio_recommended_tablets": "vol2",
    "audio_recording": "vol2",
    "audio_recording_environment": "vol2",
    "audio_recording_further_considerations": "vol2",
    "audio_recording_process": "vol2",
    "audio_setup_content": "vol2",
    "audio_setup_h2n": "vol2",
    "audio_setup_keyboard_shortcuts_audacity": "vol2",
    "audio_setup_keyboard_shortcuts_ocenaudio": "vol2",
    "audio_setup_ocenaudio": "vol2",
    "audio_setup_team": "vol2",
    "audio_signal_path": "vol2",
    "audio_signal_to_noise": "vol2",
    "audio_software": "vol2",
    "audio_software_file_renaming": "vol2",
    "audio_software_file_sharing": "vol2",
    "audio_software_format_conversion": "vol2",
    "audio_software_metadata_encoding": "vol2",
    "audio_software_recording_editing": "vol2",
    "audio_software_workspace": "vol2",
    "audio_standard_characteristics": "vol2",
    "audio_standard_file_naming": "vol2",
    "audio_standard_format": "vol2",
    "audio_standard_license": "vol2",
    "audio_standard_style": "vol2",
    "audio_studio_environment": "vol2",
    "audio_the_checker": "vol2",
    "audio_the_coordinator": "vol2",
    "audio_the_narrator": "vol2",
    "audio_the_recordist": "vol2",
    "audio_vision_purpose": "vol2",
    "audio_waveform_editor": "vol2",
    "audio_workspace_layout": "vol2",
    "excellence_in_audio": "vol2",
    "simplicity_in_audio": "vol2",
    "skills_training_in_audio": "vol2",
    "alphabet": "vol2",
    "formatting": "vol2",
    "headings": "vol2",
    "punctuation": "vol2",
    "spelling": "vol2",
    "verses": "vol2",
    "vol2_backtranslation": "vol2",
    "vol2_backtranslation_guidelines": "vol2",
    "vol2_backtranslation_kinds": "vol2",
    "vol2_backtranslation_purpose": "vol2",
    "vol2_backtranslation_who": "vol2",
    "vol2_backtranslation_written": "vol2",
    "vol2_intro": "vol2",
    "vol2_steps": "vol2",
    "vol2_things_to_check": "vol2",
    "check_notes": "vol2",
    "check_udb": "vol2",
    "check_ulb": "vol2",
    "gl_adaptulb": "vol2",
    "gl_done_checking": "vol2",
    "gl_notes": "vol2",
    "gl_questions": "vol2",
    "gl_translate": "vol2",
    "gl_udb": "vol2",
    "gl_ulb": "vol2",
    "gl_words": "vol2",
    "figs_123person": "vol2",
    "figs_abstractnouns": "vol2",
    "figs_activepassive": "vol2",
    "figs_apostrophe": "vol2",
    "figs_distinguish": "vol2",
    "figs_doublenegatives": "vol2",
    "figs_doublet": "vol2",
    "figs_ellipsis": "vol2",
    "figs_euphemism": "vol2",
    "figs_exclusive": "vol2",
    "figs_gendernotations": "vol2",
    "figs_genericnoun": "vol2",
    "figs_genitivecase": "vol2",
    "figs_go": "vol2",
    "figs_grammar": "vol2",
    "figs_hendiadys": "vol2",
    "figs_hyperbole": "vol2",
    "figs_inclusive": "vol2",
    "figs_informremind": "vol2",
    "figs_litotes": "vol2",
    "figs_merism": "vol2",
    "figs_metonymy": "vol2",
    "figs_parallelism": "vol2",
    "figs_partsofspeech": "vol2",
    "figs_personification": "vol2",
    "figs_pluralpronouns": "vol2",
    "figs_quotations": "vol2",
    "figs_rpronouns": "vol2",
    "figs_sentences": "vol2",
    "figs_singularpronouns": "vol2",
    "figs_synecdoche": "vol2",
    "figs_synonparallelism": "vol2",
    "figs_verbs": "vol2",
    "figs_youformal": "vol2",
    "guidelines_authoritative": "vol2",
    "guidelines_collaborative": "vol2",
    "guidelines_equal": "vol2",
    "guidelines_faithful": "vol2",
    "guidelines_historical": "vol2",
    "guidelines_ongoing": "vol2",
    "translate_bibleorg": "vol2",
    "translate_chapverse": "vol2",
    "translate_fraction": "vol2",
    "translate_manuscripts": "vol2",
    "translate_numbers": "vol2",
    "translate_ordinal": "vol2",
    "translate_original": "vol2",
    "translate_symaction": "vol2",
    "translate_textvariants": "vol2",
    "translate_versebridge": "vol2",
    "writing_background": "vol2",
    "writing_connectingwords": "vol2",
    "writing_intro": "vol2",
    "writing_newevent": "vol2",
    "writing_participants": "vol2",
    "writing_poetry": "vol2",
    "writing_proverbs": "vol2",
    "writing_quotations": "vol2",
    "writing_symlanguage": "vol2"
}
