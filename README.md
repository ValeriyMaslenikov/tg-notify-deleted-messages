# About

`tg-notify-deleted-messages` allows you to track messages, which were deleted by
your interlocutors. After deleting, they will be stored in "Saved Messages" with
metadata about the sender.

It also supports attachments, without storing them on your disk.


## Configuration

To authenticate your account, use command:
```
docker-compose run app python ./monitor.py auth
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

`tg-notify-deleted-messages` store messages history for past 2 days and 6 hours.
The application supports attachments, but don't store it.
Be careful, your messages can fill your disk space.

## Security

Please, don't run this application on servers, where other persons have access to. Messages history and credentials stores in an
insecure SQLite database.