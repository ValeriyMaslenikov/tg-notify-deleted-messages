import getpass
import logging
import os
import pickle
import signal
import sqlite3
import sys
import time

from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from dotenv import load_dotenv

from telethon import events, TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Message

MINUTES_PER_HOUR = 60
SECONDS_PER_MINUTE = 60

# Loading environment variables
env_path = Path(".") / ".env"

if os.path.isfile(env_path):
    load_dotenv(dotenv_path=env_path)

# Configure logging level
logging.basicConfig(level=os.getenv("LOGGING_LEVEL", logging.INFO))

# Cleaning database interval
# 2 days by documentation and + 6 hours by practice
MESSAGE_SAVING_PERIOD_SECONDS = 54 * MINUTES_PER_HOUR * SECONDS_PER_MINUTE

if os.getenv("TELEGRAM_API_ID") is None or os.getenv("TELEGRAM_API_HASH") is None:
    print('Please, read `README.md` and create `.env` file with telegram API credentials')
    exit(1)

# Telegram API
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("db/user", TELEGRAM_API_ID, TELEGRAM_API_HASH)
assert client.connect()

# Auth
if len(sys.argv) > 1 and sys.argv[1] == 'auth':
    if client.is_user_authorized():
        confirmation = input('Do you really want to delete current session and authorize new? [y/n]: ')
        if confirmation.lower() != 'y':
            exit(0)

    phone_number = input("Enter phone number: ")
    client.send_code_request(phone_number)

    try:
        client.sign_in(phone_number, input("Enter code: "))
    except SessionPasswordNeededError:
        client.sign_in(password=getpass.getpass())

    if client.is_user_authorized():
        print('Something went wrong, please, retry')
        exit(1)

    exit(0)

# Daemon
if not client.is_user_authorized():
    print('Please, execute `auth` command before starting the daemon (see README.md file)')
    exit(1)

# Database connection, table and indices creation
conn = sqlite3.connect("db/messages.db", check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS messages
             (message_id INTEGER PRIMARY KEY, message BLOB, created DATETIME)""")

c.execute("CREATE INDEX IF NOT EXISTS messages_created_index ON messages (created DESC)")

conn.commit()

# Configure handlers
client.updates.workers = 1


@client.on(events.NewMessage(incoming=True))
def handler(event: events.NewMessage.Event):
    c.execute("INSERT INTO messages (message_id, message, created) VALUES (?, ?, ?)",
              (event.message.id, sqlite3.Binary(pickle.dumps(event.message)), str(datetime.now())))
    conn.commit()


@client.on(events.MessageDeleted())
def handler(event: events.MessageDeleted.Event):
    db_result = c.execute("SELECT message_id, message FROM messages WHERE message_id IN ({0})".format(
        ",".join(str(e) for e in event.deleted_ids))).fetchall()

    messages: List[Message] = [pickle.loads(i[1]) for i in db_result]

    log_deleted_usernames = []

    for message in messages:
        user_request = client(GetFullUserRequest(message.from_id))
        user = user_request.user

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

        log_deleted_usernames.append(mention_username + "(" + str(user.id) + ")")

        text = "** Deleted message from: **[{username}](tg://user?id={id})\n".format(
            username=mention_username, id=user.id)

        if message.message:
            text += "** Message: **" + message.message

        client.send_message(
            "me",
            text,
            file=message.media
        )

    logging.info(
        "Got {deleted_messages_count} deleted messages. Has in DB {db_messages_count}. Users: {users}".format(
            deleted_messages_count=str(len(event.deleted_ids)),
            db_messages_count=str(len(messages)),
            users=", ".join(log_deleted_usernames))
    )


client.start()


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


if __name__ == "__main__":
    killer = GracefulKiller()
    while True:
        time.sleep(1)

        # Every minute clean DB
        if int(datetime.now().timestamp()) % SECONDS_PER_MINUTE == 0:
            delete_from_time = str(datetime.now() - timedelta(seconds=MESSAGE_SAVING_PERIOD_SECONDS))
            c.execute("DELETE FROM messages WHERE created < ?", (delete_from_time,))
            logging.info(
                "Deleted {count} messages older than {time} from DB".format(count=c.rowcount, time=delete_from_time))

        if killer.kill_now:
            break
