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

It uses setxkbmap to tell the window manager to do stuff differently, so
it will not work in ttys, and it won't interact with any other module of
key-mapper.

workflow:
1. injector preparation sees that "a" maps to "b"
2. check which keycode "b" would usually be
   2.1 if not in the system_mapping, find a free code
3. in the symbols file map that code to "b"
4. the system_mapping gets updated if a free keycode had to be used
5. the injection proceeds to prepare the remaining stuff using the
   updated system_mapping. The newly created key-mapper device gets the
   config files applied using setxkbmap

injection:
1. running injection sees that "a" was clicked on the keyboard
2. the injector knows based on the system_mapping that this maps to
   e.g. 48 (KEY_B) and injects it
3. the window manager sees code 48 and writes a "b" into the focused
   application, because the xkb config tells it to do so

now it is possible to map "ö" on an us keyboard

Resources:
[1] https://wiki.archlinux.org/index.php/Keyboard_input
[2] http://people.uleth.ca/~daniel.odonnell/Blog/custom-keyboard-in-linuxx11
[3] https://www.x.org/releases/X11R7.7/doc/xorg-docs/input/XKB-Enhancing.html
"""


from keymapper.logger import logger
from keymapper.paths import get_preset_path
from keymapper.state import system_mapping


def generate_xkb_config(device, mapping):
    """Generate the needed config file for apply_xkb_config.

    Parameters
    ----------
    device : string
        Name of the device
    mapping : Mapping
    """
    # List containing all keycodes that are going to be written by
    # key-mapper. Those codes are the EV_KEY capabilities of the device that
    # key-mapper creates. They will be received by the window manager.
    key_capabilities = []  # TODO

    # TODO parse macros? it would be nice if the constructor of injector would
    #   parse them once and then just change the handler somehow.
    #   I don't want to parse them a million times each time the injection
    #   starts

    # TODO describe the problem with mapping shift to e.g. 12 to explain
    #   why the new config should match the system layout as much as
    #   possible

    symbols = {}
    # TODO test
    for target_code in key_capabilities:
        target_key = system_mapping.get_key(target_code)
        if target_key is not None:
            # might be 'KEY_F24', 'odiaeresis' or 'a'
            symbols[target_code] = target_key.lower().replace('key_', '')
        else:
            # this key is not supported by the system layout, for example
            # 'odiaeresis' on an US keyboard. Find a

    # TODO if no keycode free anymore, log error and skip the rest



def apply_xkb_config(device):
    """Call setxkbmap to apply a different xkb keyboard layout to a device.

    Parameters
    ----------
    device : string
        Name of the device
    """
    # TODO test
