import re
import copy

def parse_media(media, content_version, project_chapters):
    """
    Converts a media object into formats usable in the catalog
    :param media: the media object
    :type media: dict
    :param content_version: the current version of the source content
    :type content_version: string
    :param project_chapters: a dictionary of project chapters
    :type  project_chapters: dict
    :return: resource_formats, project_formats a list of resource formats and dictionary of project formats
    """
    resource_formats = []
    project_formats = {}

    if 'resource' in media:
        resource_formats = _parse_resource(media['resource'], content_version)
    if 'projects' in media:
        for project in media['projects']:
            project_id = project['identifier']
            if project_id == 'obs':
                # TRICKY: obs projects always have 50 chapters
                # This allows empty projects to still publish media.
                chapters = range(1, 51)  # chapters 1..50
            else:
                chapters = []
            if project_id in project_chapters:
                chapters = project_chapters[project_id]
            project_formats[project_id] = _parse_project(project, content_version, chapters)
    return resource_formats, project_formats


def _parse_resource(resource, content_version):
    """
    Converts a resource media object into formats usable in the catalog
    :param resource: the media object
    :type resource: dict
    :param content_version: the current version of the source content
    :type content_version: string
    :return: a list of formats
    """
    source_version = _expand_keys(resource['version'], {'latest': content_version})
    formats = []
    if 'media' in resource:
        for media in resource['media']:
            media_version = _expand_keys(media['version'], {'latest': content_version})
            expansion_vars = _make_expansion_variables(media, content_version)
            if 'quality' in media and len(media['quality']) > 0:
                # build format for each quality
                for quality in media['quality']:
                    expansion_vars['quality'] = quality
                    format = _make_format(source_version=source_version,
                                                        media_version=media_version,
                                                        quality=quality,
                                                        media=media,
                                                        expansion_vars=expansion_vars)
                    formats.append(format)
            else:
                # build a single format
                format = _make_format(source_version=source_version,
                                                    media_version=media_version,
                                                    quality=None,
                                                    media=media,
                                                    expansion_vars=expansion_vars)
                formats.append(format)
    return formats


def _make_format(source_version, media_version, quality, media, expansion_vars):
    format = {
        'format': '',
        'modified': '',
        'size': 0,
        'source_version': '{}'.format(source_version),
        'version': '{}'.format(media_version),
        'contributor': media['contributor'],
        'url': _expand_keys(media['url'], expansion_vars),
        'signature': '',
        'build_rules': [
            'signing.sign_given_url'
        ]
    }
    if quality:
        format['quality'] = quality
    return format


def _parse_project(project, content_version, chapters_ids):
    """
    Converts a project media object into formats usable in the catalog
    :param project: the media object
    :type project: dict
    :param content_version: the current version of the source content
    :type content_version: string
    :param chapters_ids: a list of chapter identifiers in the project
    :type chapters_ids: list
    :return: a list of formats
    """
    source_version = _expand_keys(project['version'], {'latest': content_version})
    formats = []
    if 'media' in project:
        for media in project['media']:
            media_version = _expand_keys(media['version'], {'latest': content_version})
            expansion_vars = _make_expansion_variables(media, content_version)
            if 'quality' in media and len(media['quality']) > 0:
                # build format for each quality
                for quality in media['quality']:
                    expansion_vars['quality'] = quality
                    format = _make_format(source_version=source_version,
                                                        media_version=media_version,
                                                        quality=quality,
                                                        media=media,
                                                        expansion_vars=expansion_vars)
                    chapters = _prepare_chapter_formats(media, chapters_ids, expansion_vars)
                    if chapters:
                        format['chapters'] = chapters

                    formats.append(format)

            else:
                # build single format
                format = _make_format(source_version=source_version,
                                                    media_version=media_version,
                                                    quality=None,
                                                    media=media,
                                                    expansion_vars=expansion_vars)
                chapters = _prepare_chapter_formats(media, chapters_ids, expansion_vars)
                if chapters:
                    format['chapters'] = chapters

                formats.append(format)
    return formats



def _prepare_chapter_formats(media, chapters, expansion_vars):
    """
    This is a wrapper around the method `_parse_project_chapter`.
    Since we routinely conditionally prepare chapters in multiple places
    this handles it in one place
    :param media: the media object to inspect
    :param chapters: a list of chapter ids
    :param expansion_vars: a dictionary of variables that may be expanded in the chapter url
    :return:
    """
    if 'chapter_url' in media:
        chapter_url = _expand_keys(media['chapter_url'], expansion_vars)
        chapters = _parse_project_chapter(chapter_url, chapters)
        if chapters:
            return chapters
    return None


def _parse_project_chapter(chapter_url, chapters):
    """
    Generates chapter formats for use in the catalog
    :param chapter_url: the url template that will be used in the formats
    :param chapters: a list of chapter ids
    :type chapters: list
    :return:
    """
    # TODO: this requires that we give a well formatted list of chapter ids and  check if the Rc is a book
    # only book RCs can have chapter formats
    formats = []
    for chapter_id in chapters:
        format = {
            'size': 0,
            'length': 0,
            'modified': '',
            'identifier': chapter_id,
            'url': _expand_keys(chapter_url, {'chapter': chapter_id}),
            'signature': '',
            'build_rules': [
                'signing.sign_given_url'
            ]
        }
        formats.append(format)
    return formats



def _make_expansion_variables(media_block, content_version):
    """
    Creates a dictionary of expansion variables for media items.
    :param self:
    :param media_block:
    :param content_version:
    :return:
    """
    vars = copy.copy(media_block)

    # strip black listed keys
    black_list = ['url', 'chapter_url']
    for key in black_list:
        if key in vars:
            del vars[key]

    # TRICKY: using `latest` as an expansion variable in urls is not explicitly stated in the spec,
    # but it's a common misunderstanding so we allow it.
    vars['latest'] = '{}'.format(content_version)

    return vars



def _expand_keys(target, replacements):
    """
    Replaces all the dict keys found in the string with the dict values.
    Keys in the string must be delimited by brackets {}
    :param target:
    :param replacements:
    :return:
    """
    if isinstance(target, basestring) or isinstance(target, str):
        result = target
        if not isinstance(replacements, dict):
            raise Exception('Expected dictionary of replacements but received {}'.format(type(replacements)))
        for key in replacements:
            if not isinstance(replacements[key], list):
                result = re.sub(r'{\s*' + key + '\s*}', '{}'.format(replacements[key]), result)
        return result
    elif isinstance(target, int):
        return target
    else:
        raise Exception('Invalid replacement target "{}". Expected string but received {}'.format(target, type(target)))
