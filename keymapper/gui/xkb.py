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


"""Handles calls to setxkbmap. See injection/xkb.py for more info."""


import os
import subprocess
import time

from keymapper.logger import logger
from keymapper.state import custom_mapping
from keymapper.getdevices import get_mapping_device_name
from keymapper.injection.xkb import get_xkb_symbols_name


def get_device_id(device):
    """Return the device ID as known to the display server.

    Can be used in setxkbmap.

    Parameters
    ----------
    device : string
        Device name as indexed in get_devices
    """
    try:
        names = subprocess.check_output(['xinput', 'list', '--name-only'])
        names = names.decode().split('\n')
        ids = subprocess.check_output(['xinput', 'list', '--id-only'])
        ids = ids.decode().split('\n')
    except subprocess.CalledProcessError as error:
        # systemd services and ttys can't do that
        logger.error(str(error))
        return None

    mapped_name = get_mapping_device_name(device)
    for name, id in zip(names, ids):
        if name == mapped_name:
            device_id = id
            break
    else:
        logger.error('Failed to get device ID for "%s"', mapped_name)
        return None

    return device_id


def apply_xkb_config(device):
    """Call setxkbmap to apply a different xkb keyboard layout to a device.

    Parameters
    ----------
    device : string
        Device name as indexed in get_devices
    """
    # TODO test
    if not custom_mapping.get('generate_xkb_config'):
        return

    # needs at least 0.4 seconds for me until the mapping device is visible
    # in xinput
    time.sleep(1)

    name = get_xkb_symbols_name(device)
    path = f'/usr/share/X11/xkb/symbols/{name}'

    if not os.path.exists(path):
        # TODO ask the daemon if applying is needed? Or just check if a
        #  symbols file exists?
        logger.debug(
            'Symbols file "%s" doesn\'t exist, not using setxkbmap',
            path
        )
        return

    logger.info('Applying xkb configuration')

    # XkbBadKeyboard: wrong -device id
    device_id = get_device_id(device)
    if device_id is None:
        return

    cmd = [
        'setxkbmap',
        '-keycodes', 'key-mapper-keycodes',
        '-symbols', name,
        '-device', str(device_id)
    ]
    logger.debug('Running "%s"', ' '.join(cmd))
    # TODO disable Popen for setxkbmap in tests
    subprocess.Popen(cmd)
