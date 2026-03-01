#!/bin/bash

set -e

__dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. ${__dir}/eventyay_common.sh

if [ ! "$DO_MEDIA_BACKUP" = "1" ] ; then
  # exit if DO_MEDIA_BACKUP is not set
  exit 0
fi

rclone copy -vv --fast-list --transfers 32 "$DATA_DIR/data" $BACKUP_REMOTE_LOCATION/$DEPLOYMENT_NAME/data


