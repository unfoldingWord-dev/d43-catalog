import os
import re
import yaml
import json
from file_utils import read_file, download_rc, remove

def index_obs(lid, rid, format, temp_dir=None, downloader=None):
    """
    Generates a JSON index of an OBS RC.
    The resulting content can be written to a file and uploaded for use in the uW 2.0 and tS 2.0 APIs
    This should contain a single file per chapter.
    :param lid:
    :param rid:
    :param format:
    :param temp_dir: The temporary directory where files will be generated
    :param downloader: This is exposed to allow mocking the downloader
    :return: the obs json blob
    """
    obs_sources = {}
    format_str = format['format']
    if rid == 'obs' and 'type=book' in format_str:
        rc_dir = download_rc(lid, rid, format['url'], temp_dir, downloader)
        if not rc_dir: return obs_sources

        manifest = yaml.load(read_file(os.path.join(rc_dir, 'manifest.yaml')))
        dc = manifest['dublin_core']

        for project in manifest['projects']:
            pid = project['identifier']
            content_dir = os.path.join(rc_dir, project['path'])
            key = '$'.join([pid, lid, rid])
            chapters_json = _obs_chapters_to_json(os.path.normpath(content_dir))

            # app words
            app_words = {}
            app_words_file = os.path.join(rc_dir, '.apps', 'uw', 'app_words.json')
            if os.path.exists(app_words_file):
                try:
                    app_words = json.loads(read_file(app_words_file))
                except Exception as e:
                    print('ERROR: failed to load app words: {}'.format(e))

            remove(rc_dir, True)

            # TRICKY: OBS has a single project so we don't need to continue looping
            return {
                'app_words': app_words,
                'chapters': chapters_json,
                'date_modified': dc['modified'].replace('-', '').split('T')[0],
                'direction': dc['language']['direction'],
                'language': dc['language']['identifier']
            }

def __extract_chapter_number(json):
    try:
        return int(json['number'])
    except KeyError:
        return 0

def __extract_frame_id(json):
    try:
        id = json['id']
        # the second half of the id is the frame id
        return int(id.split('-')[1])
    except KeyError:
        return 0

def _obs_chapters_to_json(dir):
    """
    Converts obs chapter markdown into json
    :param dir: the obs book content directory
    :return:
    """
    chapters = []
    if os.path.isdir(dir):
        for chapter_file in os.listdir(dir):
            if chapter_file == 'config.yaml' or chapter_file == 'toc.yaml':
                continue
            chapter_slug = chapter_file.split('.md')[0]
            path = os.path.join(dir, chapter_file)
            if os.path.isfile(path):
                chapter_file = os.path.join(dir, path)
                chapter_str = read_file(chapter_file).strip()

                chapter_json = _convert_obs_chapter_to_json(chapter_str, chapter_slug, chapter_file)
                chapters.append(chapter_json)

    chapters.sort(key=__extract_chapter_number, reverse=False)
    return chapters

def _convert_obs_chapter_to_json(chapter_str, chapter_slug, chapter_file):
    """Parses an OBS chapter string (markdown) and returns a json object"""
    obs_title_re = re.compile('^\s*#+\s*(.*)', re.UNICODE)
    obs_footer_re = re.compile('\_+([^\_]*)\_+$', re.UNICODE)
    obs_image_re = re.compile('.*!\[[^\]]*\]\(.*\).*', re.IGNORECASE | re.UNICODE)

    title_match = obs_title_re.match(chapter_str)
    if title_match:
        title = title_match.group(1)
    else:
        raise Exception('Missing chapter title in OBS {}'.format(chapter_file))
    chapter_str = obs_title_re.sub('', chapter_str).strip()
    lines = chapter_str.split('\n')
    reference_match = obs_footer_re.match(lines[-1])
    if reference_match:
        reference = reference_match.group(1)
    else:
        raise Exception('Missing chapter reference in OBS {}'.format(chapter_file))
    chapter_str = '\n'.join(lines[0:-1]).strip()
    chunks = obs_image_re.split(chapter_str)

    frames = []
    chunk_index = 0
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        chunk_index += 1
        id = '{}-{}'.format(chapter_slug, '{}'.format(chunk_index).zfill(2))
        frames.append({
            'id': id,
            'img': 'https://cdn.door43.org/obs/jpg/360px/obs-en-{}.jpg'.format(id),
            'text': chunk
        })
    frames.sort(key=__extract_frame_id, reverse=False)
    return {
        'frames': frames,
        'number': chapter_slug,
        'ref': reference,
        'title': title
    }
