# -*- coding: utf-8 -*-

# Transforms old versions of manifest.json files to the latest

from __future__ import print_function, unicode_literals

import os

from datetime import datetime
from door43_tools.language_handler import Language
from general_tools.file_utils import load_json_object


class Manifest(object):
    """
    This is deprecated
    """
    PACKAGE_VERSION = 7

    def __init__(self, file_name=None, repo_name=None):
        """
        Class constructor. Optionally accepts the name of a file to deserialize.
        :param str file_name: The name of a file to deserialize into a Manifest object
        """
        # Defaults
        self.package_version = Manifest.PACKAGE_VERSION
        self.modified_at = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        self.slug = ""
        self.name = ""
        self.icon = "https://cdn.door43.org/images/default_icon.jpg"

        self.formats = []
        self.language = {}
        self.projects = []
        self.status = {}

        # deserialize
        if file_name:
            if os.path.isfile(file_name):
                try:
                    manifest_json = load_json_object(file_name)
                except Exception as e:
                    raise Exception('Structure error of the manifest.json file: {0}'.format(e))
                self.__dict__.update(manifest_json)
            else:
                raise IOError('The manifest.json file was not found')
        if repo_name:
            self.update_from_repo_name(repo_name)

    def update_from_repo_name(self, repo_name):
        if '_' in repo_name:
            parts = repo_name.split('_')
        else:
            parts = repo_name.split('-')

        if 'slug' not in self.language or not self.language['slug']:
            languages = Language.load_languages()
            for i, part in enumerate(parts):
                found = [x for x in languages if x.lc == part]
                if len(found):
                    lang = found[0]
                    self.language['slug'] = lang.lc
                    self.language['name'] = lang.ln
                    self.language['dir'] = lang.ld
                del parts[i]
                break

        for part in parts:
            if not self.slug:
                if part.lower() in ['obs', 'ulb', 'udb', 'bible', 'tn', 'tw', 'ta']:
                    if 'slug' in self.language:
                        self.slug = '{0}-{1}'.format(self.language['slug'], part.lower())
                    else:
                        self.slug = part.lower()
                    self.name = Manifest.get_resource_name(part.lower())

        if not self.slug:
            if self.language['slug']:
                parts.insert(0, self.language['slug'])
            self.slug = '-'.join(parts)

    @staticmethod
    def get_resource_name(resource_id):
        resource_id = resource_id.lower()
        if resource_id == 'ulb':
            return u'Unlocked Literal Bible'
        elif resource_id == 'udb':
            return u'Unlocked Dynamic Bible'
        elif resource_id == 'bible':
            return u'Bible'
        elif resource_id == 'obs':
            return u'Open Bible Stories'
        elif resource_id == 'tn':
            return u'translationNotes'
        elif resource_id == 'tw':
            return u'translationWords'
        elif resource_id == 'tq':
            return u'translationQuestions'
        elif resource_id == 'ta':
            return u'translationAcademy'
        return u''
