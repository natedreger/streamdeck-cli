"""Defines the Python API for interacting with the StreamDeck Configuration UI"""
import json
import os
import threading
from functools import partial
from typing import Dict, Tuple, Union, cast
from warnings import warn

from PIL import Image, ImageDraw, ImageFont
from PySide2.QtCore import Signal
from StreamDeck import DeviceManager
from StreamDeck.Devices import StreamDeck
from StreamDeck.ImageHelpers import PILHelper

from config import CONFIG_FILE_VERSION, DEFAULT_FONT, FONTS_PATH, STATE_FILE

image_cache: Dict[str, memoryview] = {}
decks: Dict[str, StreamDeck.StreamDeck] = {}
state: Dict[str, Dict[str, Union[int, Dict[int, Dict[int, Dict[str, str]]]]]] = {}
streamdecks_lock = threading.Lock()
key_event_lock = threading.Lock()


class KeySignalEmitter():
    key_pressed = Signal(str, int, bool)


streamdesk_keys = KeySignalEmitter()


def _key_change_callback(deck_id: str, _deck: StreamDeck.StreamDeck, key: int, state: bool) -> None:
    """ Callback whenever a key is pressed. This is method runs the various actions defined
        for the key being pressed, sequentially. """
    # Stream Desk key events fire on a background thread. Emit a signal
    # to bring it back to UI thread, so we can use Qt objects for timers etc.
    # Since multiple keys could fire simultaniously, we need to protect
    # shared state with a lock
    with key_event_lock:
        streamdesk_keys.key_pressed.emit(deck_id, key, state)


def _save_state():
    export_config(STATE_FILE)


def _open_config(config_file: str):
    global state

    with open(config_file) as state_file:
        config = json.loads(state_file.read())
        file_version = config.get("streamdeck_ui_version", 0)
        if file_version != CONFIG_FILE_VERSION:
            raise ValueError(
                "Incompatible version of config file found: "
                f"{file_version} does not match required version "
                f"{CONFIG_FILE_VERSION}."
            )

        state = {}
        for deck_id, deck in config["state"].items():
            deck["buttons"] = {
                int(page_id): {int(button_id): button for button_id, button in buttons.items()}
                for page_id, buttons in deck.get("buttons", {}).items()
            }
            state[deck_id] = deck


def import_config(config_file: str) -> None:
    _open_config(config_file)
    render()
    _save_state()


def export_config(output_file: str) -> None:
    try:
        with open(output_file + ".tmp", "w") as state_file:
            state_file.write(
                json.dumps(
                    {"streamdeck_ui_version": CONFIG_FILE_VERSION, "state": state},
                    indent=4,
                    separators=(",", ": "),
                )
            )
    except Exception as error:
        print(f"The configuration file '{output_file}' was not updated. Error: {error}")
        raise
    else:
        os.replace(output_file + ".tmp", os.path.realpath(output_file))


def open_decks() -> Dict[str, Dict[str, Union[str, Tuple[int, int]]]]:
    """Opens and then returns all known stream deck devices"""
    for deck in DeviceManager.DeviceManager().enumerate():
        deck.open()
        deck.reset()
        deck_id = deck.get_serial_number()
        decks[deck_id] = deck
        deck.set_key_callback(partial(_key_change_callback, deck_id))

    return {
        deck_id: {"type": deck.deck_type(), "layout": deck.key_layout()}
        for deck_id, deck in decks.items()
    }


def close_decks() -> None:
    """Closes open decks for input/ouput."""
    for _deck_serial, deck in decks.items():
        if deck.connected():
            deck.set_brightness(50)
            deck.reset()
            deck.close()


def ensure_decks_connected() -> None:
    """Reconnects to any decks that lost connection. If they did, re-renders them."""
    for deck_serial, deck in decks.copy().items():
        if not deck.connected():
            for new_deck in DeviceManager.DeviceManager().enumerate():
                try:
                    new_deck.open()
                    new_deck_serial = new_deck.get_serial_number()
                except Exception as error:
                    warn(f"A {error} error occurred when trying to reconnect to {deck_serial}")
                    new_deck_serial = None

                if new_deck_serial == deck_serial:
                    deck.close()
                    new_deck.reset()
                    new_deck.set_key_callback(partial(_key_change_callback, new_deck_serial))
                    decks[new_deck_serial] = new_deck
                    render()


def get_deck(deck_id: str) -> Dict[str, Dict[str, Union[str, Tuple[int, int]]]]:
    return {"type": decks[deck_id].deck_type(), "layout": decks[deck_id].key_layout()}


def _button_state(deck_id: str, page: int, button: int) -> dict:
    buttons = state.setdefault(deck_id, {}).setdefault("buttons", {})
    buttons_state = buttons.setdefault(page, {})  # type: ignore
    return buttons_state.setdefault(button, {})  # type: ignore

def get_button_command(deck_id: str, page: int, button: int) -> str:
    """Returns the command set for the specified button"""
    return _button_state(deck_id, page, button).get("command", "")

#ND Add
def get_button_command_type(deck_id: str, page: int, button: int) -> str:
    """Returns the command set for the specified button"""
    type = _button_state(deck_id, page, button).get("command_type", "")
    if type == '':
        type = 'Command Type'
    return type

#
def get_page(deck_id: str) -> int:
    """Gets the current page shown on the stream deck"""
    return state.get(deck_id, {}).get("page", 0)  # type: ignore

def render() -> None:
    """renders all decks"""
    for deck_id, deck_state in state.items():
        deck = decks.get(deck_id, None)
        if not deck:
            warn(f"{deck_id} has settings specified but is not seen. Likely unplugged!")
            continue

        page = get_page(deck_id)
        for button_id, button_settings in (
            deck_state.get("buttons", {}).get(page, {}).items()  # type: ignore
        ):
            key = f"{deck_id}.{page}.{button_id}"
            if key in image_cache:
                image = image_cache[key]
            else:
                image = _render_key_image(deck, **button_settings)
                image_cache[key] = image

            with streamdecks_lock:
                deck.set_key_image(button_id, image)


def _render_key_image(deck, icon: str = "", text: str = "", font: str = DEFAULT_FONT, **kwargs):
    """Renders an individual key image"""
    image = PILHelper.create_image(deck)
    draw = ImageDraw.Draw(image)

    if icon:
        try:
            rgba_icon = Image.open(icon).convert("RGBA")
        except (OSError, IOError) as icon_error:
            print(f"Unable to load icon {icon} with error {icon_error}")
            rgba_icon = Image.new("RGBA", (300, 300))
    else:
        rgba_icon = Image.new("RGBA", (300, 300))

    icon_width, icon_height = image.width, image.height
    if text:
        icon_height -= 20

    rgba_icon.thumbnail((icon_width, icon_height), Image.LANCZOS)
    icon_pos = ((image.width - rgba_icon.width) // 2, 0)
    image.paste(rgba_icon, icon_pos, rgba_icon)

    if text:
        true_font = ImageFont.truetype(os.path.join(FONTS_PATH, font), 14)
        label_w, label_h = draw.textsize(text, font=true_font)
        if icon:
            label_pos = ((image.width - label_w) // 2, image.height - 20)
        else:
            label_pos = ((image.width - label_w) // 2, (image.height // 2) - 7)
        draw.text(label_pos, text=text, font=true_font, fill="white")

    return PILHelper.to_native_format(deck, image)


if os.path.isfile(STATE_FILE):
    _open_config(STATE_FILE)
