import logging
import os
import pickle
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from telethon.events import NewMessage, MessageDeleted, MessageEdited
from telethon import TelegramClient
from telethon.hints import Entity
from telethon.tl.types import Message

CLEAN_OLD_MESSAGES_EVERY_SECONDS = 3600  # 1 hour


def load_env(dot_env_folder):
    env_path = Path(dot_env_folder) / ".env"

    if os.path.isfile(env_path):
        load_dotenv(dotenv_path=env_path)


def initialize_messages_db():
    connection = sqlite3.connect("db/messages_v2.db")
    cursor = connection.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS messages
                 (message_id INTEGER PRIMARY KEY, message_from_id INTEGER, message TEXT, media BLOB, created DATETIME)""")

    cursor.execute("CREATE INDEX IF NOT EXISTS messages_created_index ON messages (created DESC)")

    connection.commit()

    return cursor, connection


sqlite_cursor, sqlite_connection = initialize_messages_db()


async def on_new_message(event: NewMessage.Event):
    logging.info(f"Storing message from {event.message.sender_id} with {len(event.message.message)} bytes of text in DB")
    sqlite_cursor.execute(
        "INSERT INTO messages (message_id, message_from_id, message, media, created) VALUES (?, ?, ?, ?, ?)",
        (
            event.message.id,
            event.message.sender_id,
            event.message.message,
            sqlite3.Binary(pickle.dumps(event.message.media)),
            # event.message.date would also be an option here 🤔
            str(datetime.now())))
    sqlite_connection.commit()


async def update_message_content(event: NewMessage.Event):
    logging.info(f"Updating message with id {event.message.id} in DB")
    sqlite_cursor.execute(
        "UPDATE messages SET message=?, media=?, created=? WHERE message_id=?", (
            event.message.message,
            sqlite3.Binary(pickle.dumps(event.message.media)),
            str(datetime.now()),
            event.message.id
        ))
    sqlite_connection.commit()


def load_messages_by_message_ids(ids: List[int]) -> List[Message]:
    sql_message_ids = ",".join(str(id) for id in ids)

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

    return mention_username.strip()


def get_on_message_deleted(client: TelegramClient):
    async def on_message_deleted(event: MessageDeleted.Event):
        messages = load_messages_by_message_ids(event.deleted_ids)

        log_deleted_usernames = []

        for message in messages:
            user = await client.get_entity(message['message_from_id'])
            mention_username = await get_mention_username(user)

            log_deleted_usernames.append(f"{mention_username} ({str(user.id)})")
            text = "🔥🤫🤐🤭🙊🔥 **Deleted message** User: [{username}](tg://user?id={id})\n".format(
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


def get_on_message_edited(client: TelegramClient, me_id):

    async def on_message_edited(event: MessageEdited.Event):
        messages = load_messages_by_message_ids([event.message.id])
        if not len(messages):
            logging.warning(f"Message id {event.message.id} not found in local SQlite db")
            return

        # we only gave one message id, hence we can only get one result
        edited_msg = messages[0]

        user = await client.get_entity(edited_msg['message_from_id'])
        mention_username = await get_mention_username(user)

        text = f"🔄🔄🔄👀👀👀 **Edited message** User: [{mention_username}](tg://user?id={user.id})\n"

        if edited_msg['message']:
            text += f"**Old message:** {edited_msg['message']}\n"
        if event.message.message:
            text += f"**New message**: {event.message.message}\n"
        if edited_msg['message'] and event.message.message:
            await update_message_content(event)

        # We put the following two ifs here because we _do_ want the update in the DB to happen
        # and only intercept right before send_message is triggered, should either criterion apply

        if me_id == event.message.sender_id:
            """ Changes that were done by the user ID running this application do not require a notification. """
            logging.info(f"Skipping edit notification because edit is from application user themselves")
            return

        if edited_msg['message'] == event.message.message:
            """ Sometimes we get edit events even though the content has not changed at all.
                This can happen if a reaction on a message changed.
                But since this is not a real edit, we don't want to notify in this case.
            """
            logging.info(f"Skipping edit notification from user {mention_username} ({str(user.id)}) because "
                         f"message text did not change")
            return

        await client.send_message(
            "me",
            text,
            file=edited_msg['media']
        )

        logging.info(f"Handling edited message from user: {mention_username} ({str(user.id)})")

    return on_message_edited


async def cycled_clean_old_messages():
    messages_ttl_days = int(os.getenv('MESSAGES_TTL_DAYS', 14))

    while True:
        delete_from_time = str(datetime.now() - timedelta(days=messages_ttl_days))
        sqlite_cursor.execute("DELETE FROM messages WHERE created < ?", (delete_from_time,))
        logging.info(
            f"Deleted {sqlite_cursor.rowcount} messages older than {delete_from_time} from DB"
        )

        await asyncio.sleep(CLEAN_OLD_MESSAGES_EVERY_SECONDS)
