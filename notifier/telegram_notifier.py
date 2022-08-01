# -*- coding: utf-8 -*-
from collections import defaultdict
import json
import random
import sys
import os
from typing import Dict, List, Set, Tuple

import telegram

STATE_FILE = "state.json"
CREDENTIALS_FILE = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "telegram_credentials.json"
)


def _send_message(message, tc):
    bot = telegram.Bot(token=tc["bot_token"])
    print(
        bot.sendMessage(
            chat_id=tc["chat_id"],
            text=message,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
    )
    print("The following was sent: ")
    print()
    print(message)


def flattened_sites(state: dict) -> List[Tuple]:
    result = []

    for park_id in state:
        for site_id in state[park_id]["available_sites"]:
            for available_dates in state[park_id]["available_sites"][site_id]:
                result.append(
                    (
                        park_id,
                        site_id,
                        available_dates["start"],
                        available_dates["end"],
                    )
                )

    return result


def state_difference(old_state: dict, new_state: dict) -> Tuple[set, set, set]:
    flat_old = set(flattened_sites(old_state))
    flat_new = set(flattened_sites(new_state))
    flat_added = flat_new - flat_old
    flat_removed = flat_old - flat_new
    flat_same = flat_old & flat_new

    return flat_added, flat_removed, flat_same


def unflatten_sites(flat_sites):
    result = defaultdict(dict)

    for park_id, site_id, start_date, end_date in flat_sites:
        if site_id not in result[park_id]:
            result[park_id][site_id] = []

        result[park_id][site_id].append((start_date, end_date))

    return result


def generate_update_submessage(
    flat_info: Set[Tuple], park_id_to_name: Dict[str, str]
) -> str:
    unflattened_info = unflatten_sites(flat_info)
    message = ""

    for park_id in sorted(unflattened_info):
        message += f"[{park_id_to_name[park_id]}](https://www.recreation.gov/camping/campgrounds/{park_id}):\n"
        for site_id in sorted(unflattened_info[park_id]):
            message += f"  [Site {site_id}](https://www.recreation.gov/camping/campsites/{site_id}):\n"
            for start, end in unflattened_info[park_id][site_id]:
                start = start.replace("-", "\\-")
                end = end.replace("-", "\\-")
                message += f"    \\* {start} \\-\\> {end}\n"  # TODO add link

    return message


def generate_update_message(old_state, new_state) -> str:
    added, removed, same = state_difference(old_state, new_state)

    park_id_to_name = dict((i, new_state[i]["name"]) for i in new_state)
    park_id_to_name.update(dict((i, old_state[i]["name"]) for i in old_state))

    if not added and not removed:
        # Nothing to tell about...
        return ""

    message = ""

    if added:
        message += "*NEWLY ADDED*\\!\\!\\!\n\n"
        message += generate_update_submessage(added, park_id_to_name)
        message += "\n"

    if same:
        message += "*Still available:*\n\n"
        message += generate_update_submessage(same, park_id_to_name)
        message += "\n"

    if removed:
        message += "*No longer available:*\n\n"
        message += generate_update_submessage(removed, park_id_to_name)
        message += "\n"

    return message


def main(args, stdin):
    with open(CREDENTIALS_FILE) as f:
        tc = json.load(f)

    with open(STATE_FILE) as f:
        old_state = json.load(f)

    try:
        new_state = json.loads(stdin.read())
    except:
        _send_message("I'm broken\\! Please help :'(", tc)
        sys.exit(1)

    update_message = generate_update_message(old_state, new_state)

    if update_message:
        try:
            _send_message(update_message, tc)
            # If send successful, save the new state!
            with open(STATE_FILE, "w") as f:
                json.dump(new_state, f)

        except Exception as e:
            print(e)
            print("Unable to send message, not saving state 😞")
            sys.exit(1)

    else:
        print("No changes, not notifying 😞")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv, sys.stdin)
