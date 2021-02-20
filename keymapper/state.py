#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Create some singleton objects that are needed for the app to work."""


import re
import subprocess
import evdev

from keymapper.logger import logger
from keymapper.mapping import Mapping, DISABLE_NAME, DISABLE_CODE
from keymapper.paths import get_config_path, touch, USER


# xkb uses keycodes that are 8 higher than those from evdev
XKB_KEYCODE_OFFSET = 8

XMODMAP_FILENAME = 'xmodmap'


def xmodmap_to_dict(xmodmap):
    """Transform the xmodmap to a dict of character to code.

    Parameters
    ----------
    xmodmap : str
        The complete output of `xmodmap -pke`
    """
    mappings = re.findall(r'(\d+) = (.+)\n', xmodmap.lower() + '\n')
    xmodmap_dict = {}
    for keycode, names in mappings:
        # there might be multiple, like:
        # keycode  64 = Alt_L Meta_L Alt_L Meta_L
        # keycode 204 = NoSymbol Alt_L NoSymbol Alt_L
        # Alt_L should map to code 64. Writing code 204 only works
        # if a modifier is applied at the same time.
        # So take the first one.
        name = names.split()[0]
        if name == 'nosymbol':
            # TODO test
            continue

        keycode = int(keycode) - XKB_KEYCODE_OFFSET
        xmodmap_dict[name] = keycode
        # TODO what about loaded mappings of the daemon?

    return xmodmap_dict


class SystemMapping:
    """Stores information about all available keycodes."""
    def __init__(self):
        """Construct the system_mapping."""
        self._mapping = {}  # str to int
        self._allocated_unknowns = {}  # int to str  # TODO test

        # this may contain more entries than _mapping, since _mapping
        # stores only one code per character, but a keyboard layout can
        # have one character mapped to multiple keys.
        self._occupied_keycodes = set()  # TODO test

        self.populate()

    def list_names(self):
        """Return an array of all possible names in the mapping."""
        return self._mapping.keys()

    def populate(self):
        """Get a mapping of all available names to their keycodes."""
        logger.debug('Gathering available keycodes')
        self.clear()
        xmodmap_dict = {}
        try:
            xmodmap = subprocess.check_output(
                ['xmodmap', '-pke'],
                stderr=subprocess.STDOUT
            ).decode()

            xmodmap_dict = xmodmap_to_dict(xmodmap)
            for keycode in xmodmap_dict.values():
                self._occupied_keycodes.add(keycode)

            if USER != 'root':
                # write this stuff into the key-mapper config directory,
                # because the systemd service won't know the user sessions
                # xmodmap
                path = get_config_path(XMODMAP_FILENAME)
                touch(path)
                with open(path, 'w') as file:
                    # TODO test instead of xmodmap.json just store the xmodmap
                    #  output unmodified, otherwise I can't get the modified
                    #  keys here.
                    logger.debug('Writing "%s"', path)
                    file.write(xmodmap)

        except (subprocess.CalledProcessError, FileNotFoundError):
            # might be within a tty
            pass

        self._mapping.update(xmodmap_dict)

        for name, ecode in evdev.ecodes.ecodes.items():
            if name.startswith('KEY') or name.startswith('BTN'):
                self._set(name, ecode)

        self._set(DISABLE_NAME, DISABLE_CODE)

    def update(self, mapping):
        """Update this with new keys.

        Parameters
        ----------
        mapping : dict
            maps from name to code. Make sure your keys are lowercase.
        """
        self._mapping.update(mapping)

    def _set(self, name, code):
        """Map name to code."""
        self._mapping[str(name).lower()] = code

    def get(self, name):
        """Return the code mapped to the key."""
        return self._mapping.get(str(name).lower())

    def get_key(self, code):
        """Return the key that maps to the provided code."""
        # TODO test
        for key in self._mapping:
            if self._mapping[key] == code:
                return key
        return None

    def get_or_allocate(self, character):
        """Get a code to inject for that character.

        If that character does not exist in the systems keyboard layout,
        remember it and return a free code for that to use.

        Without modifying the keyboard layout of the device injecting the
        returned code won't do anything.

        Parameters
        ----------
        character : string
            For example F24 or odiaeresis
        """
        # TODO test
        character = str(character).lower()

        if character in self._mapping:
            # check if part of the system layout
            return self._mapping[character]

        for key, code in self._allocated_unknowns.items():
            # check if already asked to allocate before
            if key == character:
                return code

        for code in range(1, 256):
            # find a free keycode in the range of working keycodes
            # TODO test that keys like key_zenkakuhankaku from the linux
            #  headers are ignored when finding free codes. only the xmodmap
            #  layout is relevant
            if code in self._occupied_keycodes:
                continue

            self._allocated_unknowns[character] = code
            logger.debug('Using %s for "%s"', code, character)
            return code

        return None

    def clear(self):
        """Remove all mapped keys. Only needed for tests."""
        keys = list(self._mapping.keys())
        for key in keys:
            del self._mapping[key]

    def get_unknown_mappings(self):
        """Return a mapping of unknown characters to codes.

        For example, odiaeresis is unknown on US keyboards. The code
        in that case is just any code that was not used by the systems
        keyboard layout.
        """
        # TODO test
        return self._allocated_unknowns


# one mapping object for the GUI application
custom_mapping = Mapping()

# this mapping represents the xmodmap output, which stays constant
system_mapping = SystemMapping()
