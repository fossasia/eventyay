#!/bin/bash

set -e

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. ${__dir}/eventyay_common.sh

if [ ! "$DO_DB_BACKUP" = "1" ] ; then
  # exit if DO_DB_BACKUP is not set
  exit 0
fi

cd "$BACKUP_LOCAL_LOCATION"
backup_file=eventyay-${DEPLOYMENT_NAME}-$(date +%y-%m-%d_%H:%M).bak
docker exec eventyay-next-db pg_dump -U $EVY_POSTGRES_USER $EVY_POSTGRES_DB > $backup_file
gzip -9 $backup_file
fdupes . -d -N
rclone copy -vv --fast-list --transfers 32 . $BACKUP_REMOTE_LOCATION/$DEPLOYMENT_NAME/db
find . -mtime +7 -delete

