#!./venv/bin/python3

"""Defines the QT powered interface for configuring Stream Decks"""
import os
import shlex
import sys
import time
import json
from functools import partial
from subprocess import Popen  # nosec - Need to allow users to specify arbitrary commands

import api

from StreamDeck.DeviceManager import DeviceManager

# ND Add
# Physical Device
def handle_keypress(deck_id: str, key: int, state: bool) -> None:
    internal_command = {}
    external_command = {}
    external_commands = ['OSC', 'MIDI', 'MQTT']
    if state:
        if dimmers[deck_id].reset():
            return

        keyboard = Controller()
        page = api.get_page(deck_id)

        if api.get_button_command_type(deck_id, page, key) in external_commands:
            external_command = {"command_type":api.get_button_command_type(deck_id, page, key), "command_string":api.get_button_command_string(deck_id, page, key)}
        else:
            internal_command = {"command_type":api.get_button_command_type(deck_id, page, key), "command_string":api.get_button_command_string(deck_id, page, key)}

        if external_command:
            # queue.put(external_command)
            # print(f"External: {external_command}")
            print(json.dumps(external_command), file = sys.stdout)

        if internal_command:
            # print(f"Internal: {internal_command}")

            command = internal_command['command_type'] == 'Command'
            if command:
                try:
                    Popen(shlex.split(internal_command['command_string']))
                except Exception as error:
                    print(f"The command '{internal_command['command_string']}' failed: {error}")

            keys = internal_command['command_type'] == 'Keystroke'
            if keys:
                keys = internal_command['command_string']
                keys = keys.strip().replace(" ", "")
                for section in keys.split(","):
                    # Since + and , are used to delimit our section and keys to press,
                    # they need to be substituted with keywords.
                    section_keys = [_replace_special_keys(key_name) for key_name in section.split("+")]

                    # Translate string to enum, or just the string itself if not found
                    section_keys = [
                        getattr(Key, key_name.lower(), key_name) for key_name in section_keys
                    ]

                    for key_name in section_keys:
                        if isinstance(key_name, str) and key_name.startswith("delay"):
                            sleep_time_arg = key_name.split("delay", 1)[1]
                            if sleep_time_arg:
                                try:
                                    sleep_time = float(sleep_time_arg)
                                except Exception:
                                    print(f"Could not convert sleep time to float '{sleep_time_arg}'")
                                    sleep_time = 0
                            else:
                                # default if not specified
                                sleep_time = 0.5

                            if sleep_time:
                                try:
                                    time.sleep(sleep_time)
                                except Exception:
                                    print(f"Could not sleep with provided sleep time '{sleep_time}'")
                        else:
                            try:
                                keyboard.press(key_name)
                            except Exception:
                                print(f"Could not press key '{key_name}'")

                    for key_name in section_keys:
                        if not (isinstance(key_name, str) and key_name.startswith("delay")):
                            try:
                                keyboard.release(key_name)
                            except Exception:
                                print(f"Could not release key '{key_name}'")

            write = internal_command['command_type'] == "Text"
            if write:
                try:
                    keyboard.type(internal_command['command_string'])
                except Exception as error:
                    print(f"Could not complete the write command: {error}")

            # Set absolute brightness
            set_brightness = internal_command['command_type'] == 'Set Brightness'
            if set_brightness:
                try:
                    api.set_brightness(deck_id, int(internal_command['command_string']))
                    dimmers[deck_id].brightness = api.get_brightness(deck_id)
                    dimmers[deck_id].reset()
                except Exception as error:
                    print(f"Could not change brightness: {error}")

            # Dim by percentage
            change_brightness = internal_command['command_type'] == 'Brightness'
            if set_brightness:
                try:
                    api.change_brightness(deck_id, int(internal_command['command_string']))
                    dimmers[deck_id].brightness = api.get_brightness(deck_id)
                    dimmers[deck_id].reset()
                except Exception as error:
                    print(f"Could not change brightness: {error}")

            switch_page = internal_command['command_type'] == 'Page'
            if switch_page:
                api.set_page(deck_id, int(internal_command['command_string']) - 1)

            CloseStreamDeck = internal_command['command_type'] == 'CloseStreamDeck'
            if CloseStreamDeck:
                api.close_decks()
                sys.exit()

def start() -> None:
    # api.streamdesk_keys.key_pressed.connect(handle_keypress)
    items = api.open_decks().items()
    print(items)
    if len(items) == 0:
        print("Waiting for Stream Deck(s)...")
        while len(items) == 0:
            time.sleep(3)
            items = api.open_decks().items()

    api.render()

if __name__ == "__main__":
    start()
