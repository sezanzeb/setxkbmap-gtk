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


"""Handles xkb config files and calls to setxkbmap.

This is optional and can be disabled via the configuration. If disabled,
outputting keys that are unknown to the system layout is impossible.

It is optional because broken xkb configs can crash the X session or screw
up the injection, and in ttys xkb configs don't have any effect.

It uses setxkbmap to tell the window manager to do stuff differently for
the injected keycodes.

workflow:
1. injector preparation sees that "a" maps to "b"
2. check which keycode "b" would usually be
   2.a if not in the system_mapping, this keycode is unknown to the
       window manager and therefore cannot be used. To fix that,
       find an integer code that is not present in system_mapping yet.
   2.b if in the system_mapping, use the existing int code.
3. in the symbols file map that code to "b"
4. the system_mapping gets updated if a free keycode had to be used  # TODO does it?
5. the injection proceeds to prepare the remaining stuff using the
   updated system_mapping (key_to_code and macros). The newly created
   key-mapper device gets the config files applied using setxkbmap

injection:
1. running injection sees that "a" was clicked on the keyboard
2. the injector knows based on the system_mapping that this maps to
   e.g. 48 (KEY_B) and injects it
3. the window manager sees code 48 and writes a "b" into the focused
   application, because the xkb config tells it to do so

now it is possible to map "ö" on an US keyboard

Resources:
[1] https://wiki.archlinux.org/index.php/Keyboard_input
[2] http://people.uleth.ca/~daniel.odonnell/Blog/custom-keyboard-in-linuxx11
[3] https://www.x.org/releases/X11R7.7/doc/xorg-docs/input/XKB-Enhancing.html

Mapping code 10 to a on device_1 and 10 to shift on device_2 may cause issues
when pressing both at the same time, More information can be found in
readme/history.md. That's why the resulting symbols file should match
the existing keyboard layout as much as possible, so that shift stays on the
code that it would usually be.
"""


import base64
import random
import os

from keymapper.logger import logger
from keymapper.paths import touch
from keymapper.state import system_mapping
from keymapper.injection.macros import is_this_a_macro


SYMBOLS_TEMPLATE = """xkb_symbols "key-mapper" {
    include "%s"
    %s
};"""

LINE_TEMPLATE = 'key <%d> { [ %s ] };'


def random_path():
    """Generate a random path in tmp."""
    # TODO test
    folder = '/tmp/key-mapper'
    filename = base64.b16encode(random.randbytes(5)).decode()
    return os.path.join(folder, filename)


def find_unknown_mappings(context):
    """Return a int->string dict for unknown injected codes.

    Mapping containing all keycodes that are going to be written by
    key-mapper that are not yet part of the system mapping.
    This also includes those keys that are written by macros.
    They will be received by the window manager.
    """
    # TODO test
    unknown_mapping = {}

    # character might be 'KEY_F24', 'odiaeresis' or 'a'

    for macro in context.macros.values():
        # TODO unknown doesn't exist yet
        for code, character in macro.unknown:
            unknown_mapping[code] = character

    # TODO for character in mapping that is not a macro (is_this_a_macro)
    #  update key_to_code if a free slot could be found

    for input_code, character in context.mapping:
        # input code is what evdev reports for the grabbed device
        if system_mapping.get(character) is None:
            if is_this_a_macro(character):
                continue

            free_output_code = 0  # which code to inject TODO find
            unknown_mapping[free_output_code] = character
            context.key_to_code[input_code] = free_output_code

    return unknown_mapping


def generate_xkb_config(context):
    """Generate the needed config file for apply_xkb_config.

    Parameters
    ----------
    context : Context

    Returns
    -------
    string
        A random path in /tmp/key-mapper/ for the symbols file. If no
        new characters that are yet unknown to the system layout are used,
        it returns None.
    """
    # TODO test
    if len(context.macros) == 0 and len(context.key_to_code) == 0:
        return None

    unknown_mapping = find_unknown_mappings(context)

    symbols = []  # list of 'key <...> {[...]};' strings
    for code, character in unknown_mapping:
        symbols.append(LINE_TEMPLATE % (code, character))

    system_mapping_locale = 'de'  # TODO figure out somehow

    path = random_path()
    while os.path.exists(path):
        path = random_path()

    touch(path)
    with open(path, 'w') as f:
        f.write(SYMBOLS_TEMPLATE % (system_mapping_locale, symbols))

    return path


def apply_xkb_config(device, path):
    """Call setxkbmap to apply a different xkb keyboard layout to a device.

    Parameters
    ----------
    device : string
        Name of the device
    """
    # TODO test
    # TODO does get_devices(include_keymapper=True) return key-mapper devices
    #   without prior refresh?
    # TODO iterate over all paths to apply the new xkb config
    pass
