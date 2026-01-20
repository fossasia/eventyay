# Setting up Eventyay from Scratch

## Assumptions

We assume in the following that a server `server` is available, root
access is available.

We assume that the server is based on Ubuntu, what we are generally using.
If you use a different distribution, several commands needs to be adjusted.

## Variables

We assume that the following variables are set:

```
USER
```

The user which will run the deployment

```
DEPLOYMENT_NAME
```

some string that can work as directory name, without and whitespace,
and preferrably within the ASCII characterset.

```
DATA_DIR
```

The location where all data (postgres, uploaded data, static files, ..)
are placed. This location MUST be readable by nginx.

```
MANAGEMENT_EMAIL
```

The email address that is responsible for the "DevOps" part of the
deployment (used for certbot/ssl, emails in case of errors, etc)


## Create the server

See above - we assume this is done

Necessary size: 4G mem, maybe 80G disk

## Log into server and update

```root@server
apt update
apt upgrade
```

## Docker install

```root@server
apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)

# Add Docker's official GPG key:
apt update
apt install ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt update


apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## Restart system

```root@server
systemctl reboot
```

## Create user $USER

Note that we have to change the readability of the $USER user homedir,
since files below it will need to be readable for the web server.

```root@server
adduser $USER
# the following is necessary that the nginx server has access to
# the data files it should server
chmod 0755 /home/$USER
```

## Create deployment data directories in `$DATA_DIR`

Reminder: We need `$USER` and `$DEPLOYMENT_NAME` begin defined!

If `$DATA_DIR` is relative (not starting with `/`), it will
be relative to `/home/$USER/$DEPLOYMENT_NAME`:

```root@server
if [[ $DATA_DIR == /* ]] ; then
  FULL_DATA_DIR=$DATA_DIR
else
  FULL_DATA_DIR=/home/$USER/$DEPLOYMENT_NAME/$DATA_DIR
fi

mkdir -p $FULL_DATA_DIR
mkdir $FULL_DATA_DIR/data
mkdir $FULL_DATA_DIR/postgres
mkdir $FULL_DATA_DIR/static
chown -R $USER:$USER $FULL_DATA_DIR
chown 100:101 $FULL_DATA_DIR/data
chmod ugo+rwx $FULL_DATA_DIR/static
```

## Install nginx

```root@server
apt install nginx ssl-cert certbot python3-certbot-nginx
```

## Set up deployment data

Note, this should run as user $USER

```$USER@server
cd /home/$USER/$DEPLOYMENT_NAME
git clone https://github.com/fossasia/eventyay.git
cd eventyay
git checkout main
cd ..
ln -s eventyay/deployment/docker-compose.yaml .
if [ ! -r .env ] ; then
  cp eventyay/deployment/env.sample .env
fi
```

***IMPORTANT: EDIT .env***

Change at least `SERVER_NAME` and the `CHANGEME` entries.

## Install the nginx entry

```root@server
cp /home/$USER/$DEPLOYMENT_NAME/eventyay/deployment/nginx/enext-direct /etc/nginx/sites-available
```

***IMPORTANT: EDIT /etc/nginx/sites-available/enext-direct***

- change `SERVER_NAME`
- change `<PATH_TO>` to the **full** path to `$DATA_DIR`


### ssl update

```
certbot -m $MANAGEMENT_EMAIL --agree-tos --nginx
```

## Install fdupes and rclone

```root@server
apt install fdupes rclone
```

## Install and edit backup files

Install the files from `server-setup/scripts/` to `/usr/local/bin`
and ensure they are 0755 permissions.


## Set up rclone for $USER

```$USER@server
mkdir -p ~/.config/rclone
```
create `.config/rclone/rclone.conf` with 0600 perm and the following content,
replacing `<ACCOUNT_ID>` and `<ACCOUNT_KEY>` with correct values.

Note that one can use a different `type` here, the outer `b2` is just a tag.
```
[backup_service]
type = b2
account = <ACCOUNT_ID>
key = <ACCOUNT_KEY>
```

## Create /var/log/eventyay

```root@server
mkdir -p /var/log/eventyay
chown $USER:$USER /var/log/eventyay
```

## Create crontab for $USER

**Edit** the `server-setup/crontab` according to the explanations there
(replace ENVFILE path and UUIDs for healthcheck) and install it as
crontab of user `$USER`.



