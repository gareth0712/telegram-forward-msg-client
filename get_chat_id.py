"""Downloads media from telegram."""
import asyncio
import logging
import os
from datetime import datetime as dt
from typing import List, Optional, Tuple, Union
import json

import pyrogram
import yaml
from pyrogram.types import Audio, Document, Photo, Video, VideoNote, Voice
from rich.logging import RichHandler

from utils.file_management import get_next_name, manage_duplicate_file
from utils.log import LogFilter
from utils.meta import print_meta
from utils.updates import check_for_updates

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)
logging.getLogger("pyrogram.session.session").addFilter(LogFilter())
logging.getLogger("pyrogram.client").addFilter(LogFilter())
logger = logging.getLogger("media_downloader")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
FAILED_IDS: list = []
DOWNLOADED_IDS: list = []


def update_config(config: dict):
    """
    Update existing configuration file.

    Parameters
    ----------
    config: dict
        Configuration to be written into config file.
    """
    config["ids_to_retry"] = (
        list(set(config["ids_to_retry"]) - set(DOWNLOADED_IDS)) + FAILED_IDS
    )
    with open("config.yaml", "w") as yaml_file:
        yaml.dump(config, yaml_file, default_flow_style=False)
    logger.info("Updated last read message_id to config file")


async def begin_import(config: dict, pagination_limit: int) -> dict:
    """
    Create pyrogram client and initiate download.

    The pyrogram client is created using the ``api_id``, ``api_hash``
    from the config and iter through message offset on the
    ``last_message_id`` and the requested file_formats.

    Parameters
    ----------
    config: dict
        Dict containing the config to create pyrogram client.
    pagination_limit: int
        Number of message to download asynchronously as a batch.

    Returns
    -------
    dict
        Updated configuration to be written into config file.
    """
    client = pyrogram.Client(
        "media_downloader",
        api_id=config["api_id"],
        api_hash=config["api_hash"],
    )
    user_id = config["user_id"]
    print(user_id)
    await client.start()
    # Get User info
    # me = await client.get_me()
    # print(me)

    # Get list of chat for chat ID
    dialogs = await client.get_dialogs()
    for dialog in dialogs:
        chat = dialog["chat"]
        chat_type = chat["type"]
        if chat_type == "private":
            print('chat type: ', chat_type, 'id: ',
                  chat["id"], '; user:', chat["first_name"])
        elif chat_type == "channel":
            print('chat type: ', chat_type, 'id: ',
                  chat["id"], '; title:', chat["title"])
        elif chat_type == 'supergroup':
            print('chat type: ', chat_type, 'id: ',
                  chat["id"], "title:", chat["title"])
        else:
            print('chat type: ', chat_type, 'id: ',
                  chat["id"], "title:", chat["title"], 'user:', chat["first_name"])
    # Save dialog to file?
    # dialogsStr = json.dumps(dialogs)
    # f = open("dialogs.json", "a")
    # f.write(dialogsStr)
    # f.close()

    await client.stop()

    return config


def main():
    """Main function of the downloader."""
    with open(os.path.join(THIS_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    updated_config = asyncio.get_event_loop().run_until_complete(
        begin_import(config, pagination_limit=100)
    )

    # update_config(updated_config)
    # check_for_updates()


if __name__ == "__main__":
    print_meta(logger)
    main()
