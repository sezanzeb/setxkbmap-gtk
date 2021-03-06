#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
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


import unittest
import asyncio

from evdev.ecodes import EV_REL, REL_X, REL_Y, REL_WHEEL, REL_HWHEEL, \
    EV_ABS, ABS_X, ABS_Y, ABS_RX, ABS_RY

from keymapper.config import config
from keymapper.mapping import Mapping
from keymapper.injection.context import Context
from keymapper.injection.event_producer import EventProducer, MOUSE, WHEEL

from tests.test import InputDevice, UInput, MAX_ABS, clear_write_history, \
    uinput_write_history, quick_cleanup, new_event, MIN_ABS


abs_state = [0, 0, 0, 0]


class TestEventProducer(unittest.TestCase):
    def setUp(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.mapping = Mapping()
        self.context = Context(self.mapping)

        uinput = UInput()
        self.context.uinput = uinput

        device = InputDevice('/dev/input/event30')
        self.event_producer = EventProducer(self.context)
        self.event_producer.set_abs_range_from(device)
        asyncio.ensure_future(self.event_producer.run())

        config.set('gamepad.joystick.x_scroll_speed', 1)
        config.set('gamepad.joystick.y_scroll_speed', 1)

    def tearDown(self):
        quick_cleanup()

    def test_debounce_1(self):
        loop = asyncio.get_event_loop()
        tick_time = 1 / 60
        history = []

        self.event_producer.debounce(1234, history.append, (1,), 10)
        asyncio.ensure_future(self.event_producer.run())
        loop.run_until_complete(asyncio.sleep(6 * tick_time))
        self.assertEqual(len(history), 0)
        loop.run_until_complete(asyncio.sleep(6 * tick_time))
        self.assertEqual(len(history), 1)
        # won't get called a second time
        loop.run_until_complete(asyncio.sleep(11 * tick_time))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0], 1)

    def test_debounce_2(self):
        loop = asyncio.get_event_loop()
        tick_time = 1 / 60
        history = []

        self.event_producer.debounce(1234, history.append, (1,), 10)
        asyncio.ensure_future(self.event_producer.run())
        loop.run_until_complete(asyncio.sleep(6 * tick_time))
        self.assertEqual(len(history), 0)
        # replaces
        self.event_producer.debounce(1234, history.append, (2,), 20)
        loop.run_until_complete(asyncio.sleep(6 * tick_time))
        self.assertEqual(len(history), 0)
        loop.run_until_complete(asyncio.sleep(11 * tick_time))
        self.assertEqual(len(history), 1)
        # won't get called a second time
        loop.run_until_complete(asyncio.sleep(21 * tick_time))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0], 2)

    def test_debounce_3(self):
        loop = asyncio.get_event_loop()
        tick_time = 1 / 60
        history = []

        self.event_producer.debounce(1234, history.append, (1,), 10)
        self.event_producer.debounce(5678, history.append, (2,), 20)
        asyncio.ensure_future(self.event_producer.run())
        loop.run_until_complete(asyncio.sleep(11 * tick_time))
        self.assertEqual(len(history), 1)
        loop.run_until_complete(asyncio.sleep(11 * tick_time))
        self.assertEqual(len(history), 2)
        loop.run_until_complete(asyncio.sleep(21 * tick_time))
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], 1)
        self.assertEqual(history[1], 2)

    def assertClose(self, a, b, within):
        """a has to be within b - b * within, b + b * within."""
        self.assertLess(a - abs(a) * within, b)
        self.assertGreater(a + abs(a) * within, b)

    def test_assertClose(self):
        self.assertClose(5, 5, 0.1)
        self.assertClose(5, 5, 1)
        self.assertClose(6, 5, 0.2)
        self.assertClose(4, 5, 0.3)
        self.assertRaises(AssertionError, lambda: self.assertClose(6, 5, 0.1))
        self.assertRaises(AssertionError, lambda: self.assertClose(4, 5, 0.1))

        self.assertClose(-5, -5, 0.1)
        self.assertClose(-5, -5, 1)
        self.assertClose(-6, -5, 0.2)
        self.assertClose(-4, -5, 0.3)
        self.assertRaises(AssertionError, lambda: self.assertClose(-6, -5, 0.1))
        self.assertRaises(AssertionError, lambda: self.assertClose(-4, -5, 0.1))

    def do(self, a, b, c, d, expectation):
        """Present fake values to the loop and observe the outcome."""
        clear_write_history()
        self.event_producer.context.update_purposes()
        self.event_producer.notify(new_event(EV_ABS, ABS_X, a))
        self.event_producer.notify(new_event(EV_ABS, ABS_Y, b))
        self.event_producer.notify(new_event(EV_ABS, ABS_RX, c))
        self.event_producer.notify(new_event(EV_ABS, ABS_RY, d))
        # 3 frames
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.sleep(3 / 60))
        history = [h.t for h in uinput_write_history]
        # sleep long enough to test if multiple events are written
        self.assertGreater(len(history), 1)
        self.assertIn(expectation, history)

        for history_entry in history:
            self.assertEqual(history_entry[:2], expectation[:2])
            # if the injected cursor movement is 19 or 20 doesn't really matter
            self.assertClose(history_entry[2], expectation[2], 0.1)

    def test_joystick_purpose_1(self):
        speed = 20
        self.mapping.set('gamepad.joystick.non_linearity', 1)
        self.mapping.set('gamepad.joystick.pointer_speed', speed)
        self.mapping.set('gamepad.joystick.left_purpose', MOUSE)
        self.mapping.set('gamepad.joystick.right_purpose', WHEEL)

        min_abs = 0
        # if `rest` is not exactly `max_abs / 2` decimal places might add up
        # and cause higher or lower values to be written after a few events,
        # which might be difficult to test.
        max_abs = 256
        rest = 128  # resting position of the cursor
        self.event_producer.set_abs_range(min_abs, max_abs)

        self.do(max_abs, rest, rest, rest, (EV_REL, REL_X, speed))
        self.do(min_abs, rest, rest, rest, (EV_REL, REL_X, -speed))
        self.do(rest, max_abs, rest, rest, (EV_REL, REL_Y, speed))
        self.do(rest, min_abs, rest, rest, (EV_REL, REL_Y, -speed))

        # vertical wheel event values are negative
        self.do(rest, rest, max_abs, rest, (EV_REL, REL_HWHEEL, 1))
        self.do(rest, rest, min_abs, rest, (EV_REL, REL_HWHEEL, -1))
        self.do(rest, rest, rest, max_abs, (EV_REL, REL_WHEEL, -1))
        self.do(rest, rest, rest, min_abs, (EV_REL, REL_WHEEL, 1))

    def test_joystick_purpose_2(self):
        speed = 30
        config.set('gamepad.joystick.non_linearity', 1)
        config.set('gamepad.joystick.pointer_speed', speed)
        config.set('gamepad.joystick.left_purpose', WHEEL)
        config.set('gamepad.joystick.right_purpose', MOUSE)
        config.set('gamepad.joystick.x_scroll_speed', 1)
        config.set('gamepad.joystick.y_scroll_speed', 2)

        # vertical wheel event values are negative
        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, 1))
        self.do(MIN_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, -1))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, -2))
        self.do(0, MIN_ABS, 0, 0, (EV_REL, REL_WHEEL, 2))

        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_X, speed))
        self.do(0, 0, MIN_ABS, 0, (EV_REL, REL_X, -speed))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_Y, speed))
        self.do(0, 0, 0, MIN_ABS, (EV_REL, REL_Y, -speed))

    def test_joystick_purpose_3(self):
        speed = 40
        self.mapping.set('gamepad.joystick.non_linearity', 1)
        config.set('gamepad.joystick.pointer_speed', speed)
        self.mapping.set('gamepad.joystick.left_purpose', MOUSE)
        config.set('gamepad.joystick.right_purpose', MOUSE)

        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_X, speed))
        self.do(MIN_ABS, 0, 0, 0, (EV_REL, REL_X, -speed))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_Y, speed))
        self.do(0, MIN_ABS, 0, 0, (EV_REL, REL_Y, -speed))

        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_X, speed))
        self.do(0, 0, MIN_ABS, 0, (EV_REL, REL_X, -speed))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_Y, speed))
        self.do(0, 0, 0, MIN_ABS, (EV_REL, REL_Y, -speed))

    def test_joystick_purpose_4(self):
        config.set('gamepad.joystick.left_purpose', WHEEL)
        config.set('gamepad.joystick.right_purpose', WHEEL)
        self.mapping.set('gamepad.joystick.x_scroll_speed', 2)
        self.mapping.set('gamepad.joystick.y_scroll_speed', 3)

        self.do(MAX_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, 2))
        self.do(MIN_ABS, 0, 0, 0, (EV_REL, REL_HWHEEL, -2))
        self.do(0, MAX_ABS, 0, 0, (EV_REL, REL_WHEEL, -3))
        self.do(0, MIN_ABS, 0, 0, (EV_REL, REL_WHEEL, 3))

        # vertical wheel event values are negative
        self.do(0, 0, MAX_ABS, 0, (EV_REL, REL_HWHEEL, 2))
        self.do(0, 0, MIN_ABS, 0, (EV_REL, REL_HWHEEL, -2))
        self.do(0, 0, 0, MAX_ABS, (EV_REL, REL_WHEEL, -3))
        self.do(0, 0, 0, MIN_ABS, (EV_REL, REL_WHEEL, 3))


if __name__ == "__main__":
    unittest.main()
