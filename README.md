# About

`tg-notify-deleted-messages` allows you to track messages, which were deleted by
your interlocutors. After deleting, they will be stored in "Saved Messages" with
metadata about the sender.

It also supports attachments, without storing them on your disk.



## Configuration

1. Go to https://my.telegram.org . Select "API development tools" and create application.
2. Copy `.env.example` file with name `.env`. Change `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`
 values.
3. Authenticate your account using command:
```
docker-compose create --force-recreate --build app && docker-compose run app python ./src/monitor.py auth
```

## Start daemon

```
docker-compose up -d app
```

## Stop daemon

```
docker-compose stop app
```

## Disk usage and attachments

`tg-notify-deleted-messages` store messages history for the time specified
in the `MESSAGES_TTL_DAYS` environment variable, with default TTL – 14 days.
You can change this interval by changing the `.env` file, or defining environment
variable at the system level.

The application supports attachments, but don't store it.
Be careful, your messages can fill your disk space.

## Security

Please, don't run this application on servers, where other persons have access to.
Messages history and credentials are stored in the insecure SQLite database.

## Roadmap

### Preload the history, when the application starts 

If you want to support the old messages, but you start this application recently,
it'll be great, if it will preload the messages in the database once it starts.

### Instead of "Saved messages", send these messages to the private channel/bot

It will allows us to receive notifications, when the message was deleted, instead of
finding these messages in the "Saved messages".

### Edits

Now the application stores only the first version of the message. It means,
that after your companion edit the message and then he will delete it, you
will receive the information about the first version of the message.

The best implementation is to store all versions of the message and receive
all of them.

### Messages versions

As soon as your companion will know that you use this tool, they will start
editing the messages, instead of deleting it. To handle it, we can store the
versions of every message, and after forwarding the original message to the bot,
it should send you the history of edits.

## Contribution

Feel free to create issues, bug reports and pull requests. I will be very
grateful, if someone will implement one of the features, described in the roadmap.
