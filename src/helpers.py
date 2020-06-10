import logging
import os
import pickle
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from telethon.events import NewMessage, MessageDeleted
from telethon import TelegramClient
from telethon.hints import Entity
from telethon.tl.types import Message

CLEAN_OLD_MESSAGES_EVERY_SECONDS = 60  # 1 minute


def load_env(dot_env_folder):
    env_path = Path(dot_env_folder) / ".env"

    if os.path.isfile(env_path):
        load_dotenv(dotenv_path=env_path)
        logging.debug('`.env` file is loaded')
    else:
        logging.debug('`.env` file is absent, using system environment variables')


def initialize_messages_db():
    connection = sqlite3.connect("db/messages_v2.db")
    cursor = connection.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS messages
                 (message_id INTEGER PRIMARY KEY, message_from_id INTEGER, message TEXT, media BLOB, created DATETIME)""")

    cursor.execute("CREATE INDEX IF NOT EXISTS messages_created_index ON messages (created DESC)")

    connection.commit()

    return cursor, connection


sqlite_cursor, sqlite_connection = initialize_messages_db()


def get_on_new_message(client: TelegramClient):
    async def on_new_message(event: NewMessage.Event):
        sqlite_cursor.execute(
            "INSERT INTO messages (message_id, message_from_id, message, media, created) VALUES (?, ?, ?, ?, ?)",
            (
                event.message.id,
                event.message.from_id,
                event.message.message,
                sqlite3.Binary(pickle.dumps(event.message.media)),
                str(datetime.now())))
        sqlite_connection.commit()

    return on_new_message


def load_messages_from_event(event: MessageDeleted.Event) -> List[Message]:
    sql_message_ids = ",".join(str(deleted_id) for deleted_id in event.deleted_ids)

    db_results = sqlite_cursor.execute(
        f"SELECT message_id, message_from_id, message, media FROM messages WHERE message_id IN ({sql_message_ids})"
    ).fetchall()

    messages = []
    for db_result in db_results:
        messages.append({
            "id": db_result[0],
            "message_from_id": db_result[1],
            "message": db_result[2],
            "media": pickle.loads(db_result[3]),
        })

    return messages


async def get_mention_username(user: Entity):
    if user.first_name or user.last_name:
        mention_username = \
            (user.first_name + " " if user.first_name else "") + \
            (user.last_name if user.last_name else "")
    elif user.username:
        mention_username = user.username
    elif user.phone:
        mention_username = user.phone
    else:
        mention_username = user.id

    return mention_username


def get_on_message_deleted(client: TelegramClient):
    async def on_message_deleted(event: MessageDeleted.Event):
        messages = load_messages_from_event(event)

        log_deleted_usernames = []

        for message in messages:
            user = await client.get_entity(message['message_from_id'])
            mention_username = await get_mention_username(user)

            log_deleted_usernames.append(mention_username + " (" + str(user.id) + ")")
            text = "🔥🔥🔥🤫🤐🤭🙊🔥🔥🔥\n**Deleted message from: **[{username}](tg://user?id={id})\n".format(
                username=mention_username, id=user.id)

            if message['message']:
                text += "**Message:** " + message['message']

            await client.send_message(
                "me",
                text,
                file=message['media']
            )

        logging.info(
            "Got {deleted_messages_count} deleted messages. Has in DB {db_messages_count}. Users: {users}".format(
                deleted_messages_count=str(len(event.deleted_ids)),
                db_messages_count=str(len(messages)),
                users=", ".join(log_deleted_usernames))
        )

    return on_message_deleted


async def cycled_clean_old_messages():
    messages_ttl_days = int(os.getenv('MESSAGES_TTL_DAYS', 14))

    while True:
        delete_from_time = str(datetime.now() - timedelta(days=messages_ttl_days))
        sqlite_cursor.execute("DELETE FROM messages WHERE created < ?", (delete_from_time,))
        logging.info(
            f"Deleted {sqlite_cursor.rowcount} messages older than {delete_from_time} from DB"
        )

        await asyncio.sleep(CLEAN_OLD_MESSAGES_EVERY_SECONDS)
