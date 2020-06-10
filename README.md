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