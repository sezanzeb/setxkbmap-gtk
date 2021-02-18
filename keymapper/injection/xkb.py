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
up the injection, and in ttys xkb configs don't have any effect. setxkbmap
is hard to work with, and xkb configs are horrible.

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
4. the "key-mapper ... mapped" uinput is created and the symbols file
   applied on it

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


import subprocess
import time

from keymapper.logger import logger
from keymapper.paths import touch
from keymapper.state import system_mapping, XKB_KEYCODE_OFFSET

SYMBOLS_TEMPLATE = """default xkb_symbols "key-mapper" {
    %s
};
"""

LINE_TEMPLATE = 'key <%d> { [ %s ] };'


def generate_xkb_config(context, name):
    """Generate the needed config file for apply_xkb_config.

    Parameters
    ----------
    context : Context
    name : string
        Used to name the file in /usr/share/X11/xkb/symbols/key-mapper.
        Existing configs with that name will be overwritten

    Returns
    -------
    string
        A name that can be used for the -symbols argument of setxkbmap
    """
    # TODO test
    if len(context.macros) == 0 and len(context.key_to_code) == 0:
        return None

    if len(system_mapping.get_unknown_mappings()) == 0:
        # there is no need to change the layout of the device
        return None

    symbols = []  # list of 'key <...> {[...]};' strings

    for character, code in context.get_all_output_characters().items():
        # TODO resolve that code in xmodmap -pke. if there, insert the
        #  modifications of that character as well
        # TODO uppercase f24 -> F24 for symbols file?
        symbols.append(LINE_TEMPLATE % (code + XKB_KEYCODE_OFFSET, character))

    name = f'key-mapper/{name}'.replace(' ', '_')
    path = f'/usr/share/X11/xkb/symbols/{name}'

    touch(path)
    with open(path, 'w') as f:
        logger.info('Writing xkb symbols "%s"', path)
        contents = SYMBOLS_TEMPLATE % '\n    '.join(symbols)
        logger.spam('"%s":\n%s', path, contents.strip())
        f.write(contents)

    return name


def apply_xkb_config(context, symbols_name):
    """Call setxkbmap to apply a different xkb keyboard layout to a device.

    Parameters
    ----------
    context : Context
    symbols_name : string
        Path of the symbols file relative to /usr/share/X11/xkb/symbols/
    """
    # needs at least 0.4 seconds for me until the mapping device is visible
    # in xinput
    time.sleep(0.4 * 2)

    # TODO test
    # TODO can this stuff even be done from within the daemon?
    logger.info('Applying xkb configuration')
    assert ' ' not in symbols_name

    device_id = None

    # find the device id. Is there really no better way than parsing stuff?
    names = subprocess.check_output(['xinput', 'list', '--name-only']).decode().split('\n')
    ids = subprocess.check_output(['xinput', 'list', '--id-only']).decode().split('\n')
    for name, id in zip(names, ids):
        if name == context.uinput.name:
            device_id = id
            break
    else:
        logger.error(
            'Failed to get device id for "%s"',
            context.uinput.name
        )
        return

    # XkbBadKeyboard: wrong -device id
    cmd = [
        'setxkbmap',
        '-keycodes', 'key-mapper-keycodes',
        '-symbols', symbols_name,
        '-device', str(device_id)
    ]
    logger.debug('Running "%s"', ' '.join(cmd))
    # TODO disable Popen for setxkbmap in tests
    subprocess.Popen(cmd)
