#!/bin/bash

set -e

if [ "x$1" = "x" ] ; then
  echo "Missing first argument for .env file" >&2
  exit 1
fi

if [ ! -r "$1" ] ; then
  echo "Cannot read .env file $1" >&2
  exit 1
fi

. "$1"

URL="$EVY_SITE_URL"

if [ "x$URL" = "x" ] ; then
  echo "Cannot find URL from EVY_SITE_URL" >&2
  exit 1
fi

SITENAME=${URL##https://}
SITENAME=${SITENAME##http://}
SITENAME=${SITENAME%%/*}
SITENAME=${SITENAME%%\.eventyay\.com}

if [ "x$SITENAME" = "x" ] ; then
  echo "Cannot find SITENAME from URL $URL" >&2
  exit 1
fi

# DB user and DB name check
if [ "x$EVY_POSTGRES_DB" = "x" ] ; then
  echo "Cannot find pg db name from EVY_POSTGRES_DB" >&2
  exit 1
fi
if [ "x$EVY_POSTGRES_USER" = "x" ] ; then
  echo "Cannot find pg db name from EVY_POSTGRES_USER" >&2
  exit 1
fi

mkdir -p /home/fossasia/backup/db
cd /home/fossasia/backup/db
backup_file=eventyay-${SITENAME}-$(date +%y-%m-%d_%H:%M).bak
docker exec eventyay-next-db pg_dump -U $EVY_POSTGRES_USER $EVY_POSTGRES_DB > $backup_file
gzip -9 $backup_file
fdupes . -d -N
rclone copy -vv --fast-list --transfers 32 . b2:eventyay-backup/$SITENAME/db
find . -mtime +7 -delete

