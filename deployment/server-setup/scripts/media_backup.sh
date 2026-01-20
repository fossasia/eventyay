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

if [ "x$DATADIR" = "x" ] ; then
  echo "Cannot find DATADIR" >&2
  exit 1
fi

if [[ $DATADIR == \./* ]] ; then
  DATADIR="$(dirname "$1")/$DATADIR"
fi

if [ ! -r "$DATADIR/data" ] ; then
  echo "Cannot find data in DATADIR=$DATADIR" >&2
  exit 1
fi

rclone copy -vv --fast-list --transfers 32 "$DATADIR/data" b2:eventyay-backup/$SITENAME/data

