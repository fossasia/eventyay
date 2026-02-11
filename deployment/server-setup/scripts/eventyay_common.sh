# Common code to parse .env file in Eventyay Management scripts

if [ "x$1" = "x" ] ; then
  echo "Missing first argument for .env file" >&2
  exit 1
fi

if [ ! -r "$1" ] ; then
  echo "Cannot read .env file $1" >&2
  exit 1
fi

ENV_FILE="$1"
shift

. "$ENV_FILE"

if [ "x$DEPLOYMENT_NAME" = "x" ] ; then
  echo "DEPLOYMENT_NAME is undefined, exiting." >&2
  exit 1
fi

if [ "xMANAGEMENT_EMAIL" = "x" ] ; then
  echo "MANAGEMENT_EMAIL is undefined, exiting." >&2
  exit 1
fi


if [ "x$DO_DB_BACKUP" = "x1" -o "x$DO_MEDIA_BACKUP" = "x1" ] ; then
  # check backup locations
  if [ "x$BACKUP_REMOTE_LOCATION" = "x" ] ; then
    echo "BACKUP_REMOTE_LOCATION is undefined, exiting." >&2
    exit 1
  fi
  if [ "x$BACKUP_LOCAL_LOCATION" = "x" ] ; then
    echo "BACKUP_LOCAL_LOCATION is undefined, exiting." >&2
    exit 1
  fi
  mkdir -p "$BACKUP_LOCAL_LOCATION"
fi

if [ "x$DATA_DIR" = "x" ] ; then
  echo "DATA_DIR is undefined, exiting." >&2
  exit 1
fi

if [[ $DATA_DIR == \./* ]] ; then
  DATA_DIR="$(dirname "$ENV_FILE")/$DATA_DIR"
fi

if [ ! -r "$DATA_DIR/data" ] ; then
  echo "Cannot find data in DATA_DIR=$DATA_DIR" >&2
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


