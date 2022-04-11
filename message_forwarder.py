import asyncio
import logging
import time
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
    with open("config.yaml", "a") as file:
        last_read_message_id = config["last_read_message_id"]
        file.write(f"last_read_message_id: {last_read_message_id}")
        # yaml.dump(config, yaml_file, default_flow_style=False)
    logger.info("Updated last read message_id to config file")


async def _get_media_meta(
    media_obj: Union[Audio, Document, Photo, Video, VideoNote, Voice],
    _type: str,
) -> Tuple[str, Optional[str]]:
    """Extract file name and file id from media object.

    Parameters
    ----------
    media_obj: Union[Audio, Document, Photo, Video, VideoNote, Voice]
        Media object to be extracted.
    _type: str
        Type of media object.

    Returns
    -------
    Tuple[str, Optional[str]]
        file_name, file_format
    """
    if _type in ["audio", "document", "video"]:
        # pylint: disable = C0301
        file_format: Optional[str] = media_obj.mime_type.split(
            "/")[-1]  # type: ignore
    else:
        file_format = None

    if _type in ["voice", "video_note"]:
        # pylint: disable = C0209
        file_format = media_obj.mime_type.split("/")[-1]  # type: ignore
        file_name: str = os.path.join(
            THIS_DIR,
            _type,
            "{}_{}.{}".format(
                _type,
                dt.utcfromtimestamp(
                    media_obj.date).isoformat(),  # type: ignore
                file_format,
            ),
        )
    else:
        file_name = os.path.join(
            THIS_DIR, _type, getattr(media_obj, "file_name", None) or ""
        )
    return file_name, file_format


async def forward_message(client, config):
    chat_id = config["chat_id"]
    last_read_message_id = config["last_read_message_id"]
    forward_to_id = config["forward_to_id"]

    messages_iter = client.iter_history(
        chat_id,
        offset_id=last_read_message_id,
        reverse=True,
    )
    messages_list: list = []
    pagination_count: int = 0

    async for message in messages_iter:  # type: ignore
        message_id = message["message_id"]
        if pagination_count != 100:
            # if pagination_count != pagination_limit:
            if message["service"]:
                continue
            pagination_count += 1
            messages_list.append(message_id)
        else:
            print('Forwarding messages', messages_list)
            forwarded_messages = await client.forward_messages(forward_to_id, chat_id, messages_list, protect_content=True)
            # Reset
            pagination_count = 0
            messages_list = []
            # Update config
            config["last_read_message_id"] = message_id
            update_config(config)
            # Avoid flood_wait_x error
            time.sleep(240)
            if message["service"]:
                continue
            messages_list.append(message_id)

    if messages_list:
        print('forwarding remaining')
        print('message list is:', messages_list)
        messages_list_last_index = len(messages_list) - 1
        last_id = messages_list[messages_list_last_index]
        forwarded_messages = await client.forward_messages(forward_to_id, chat_id, messages_list, protect_content=True)
        # Update config
        config["last_read_message_id"] = last_id + 1
        update_config(config)
        # Avoid flood_wait_x error
        time.sleep(120)


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
    # dialogs = await client.get_dialogs()
    # for dialog in dialogs:
    #     chat = dialog["chat"]
    #     chat_type = chat["type"]
    #     if chat_type == "private":
    #         print('chat type: ', chat_type, 'id: ',
    #               chat["id"], '; user:', chat["first_name"])
    #     elif chat_type == "channel":
    #         print('chat type: ', chat_type, 'id: ',
    #               chat["id"], '; title:', chat["title"])
    #     elif chat_type == 'supergroup':
    #         print('chat type: ', chat_type, 'id: ',
    #               chat["id"], "title:", chat["title"])
    #     else:
    #         print('chat type: ', chat_type, 'id: ',
    #               chat["id"], "title:", chat["title"], 'user:', chat["first_name"])
    # Save dialog to file?
    # dialogsStr = json.dumps(dialogs)
    # f = open("dialogs.json", "a")
    # f.write(dialogsStr)
    # f.close()

    # Get chat info
    # chat_info = await client.get_chat(
    #     chat_id,
    # )
    # print(chat_info)

    # Chat history [Elementary]
    # chat_history = await client.get_history(
    #     chat_id,
    # )
    # print(chat_history)

    # Forward Message [Elementary]
    # forwarded_message = await client.forward_messages(chat_id, chat_id, 4356)
    # print(forwarded_message)

    # Forward Message [Advanced]
    await forward_message(client, config)

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
