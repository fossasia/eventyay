# Creating a new server and deployment

## Assumptions

We assume that the user running the deployments is called `fossasia`.
If you want a different user, many things here need to be updated.

## Create hetzner server

## Log into server and update

```root@server
apt update
...
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

## Create fossasia user

Note that we have to change the readability of the fossasia user homedir

```root@server
adduser fossasia
# the following is necessary that the nginx server has access to
# the data files it should server
chmod 0755 /home/fossasia
```

## Create deployment data directories

The `NAME_OF_THE_DEPLOYMENT` can by any proper name for a directory,
but without spaces!

```root@server
DEPLOYMENT=<NAME_OF_THE_DEPLOYMENT>
mkdir -p /home/fossasia/$DEPLOYMENT/data
mkdir /home/fossasia/$DEPLOYMENT/data/data
mkdir /home/fossasia/$DEPLOYMENT/data/postgres
mkdir /home/fossasia/$DEPLOYMENT/data/static
chown -R fossasia:fossasia /home/fossasia/$DEPLOYMENT
chown 100:101 /home/fossasia/$DEPLOYMENT/data/data
chmod ugo+rwx /home/fossasia/$DEPLOYMENT/data/static
```

## Install nginx

```root@server
apt install nginx ssl-cert certbot python3-certbot-nginx
```

## Set up deployment data

Note, this should run as user `fossasia`

```fossasia@server
DEPLOYMENT=<NAME_OF_THE_DEPLOYMENT>
cd /home/fossasia/$DEPLOYMENT
git clone https://github.com/fossasia/eventyay.git
cd eventyay
git checkout main
cd ..
ln -s eventyay/deployment/docker-compose.yaml .
```

Create `.env` from the `sample.env` by changing `SERVER_NAME`
and all `CHANGEME` entries.

## Install the nginx entry

On the server, copy `eventyay/deployment/nginx/enext-direct` to `/etc/nginx/sites-available`

### ssl update

```
certbot -m eventyay-devops@fossasia.org --agree-tos --nginx
```

## Install fdupes and rclone

```root@server
apt install fdupes rclone
```

## Install and edit backup files

Install the files from `server-setup/scripts/` to `/usr/local/bin`
and ensure they are 0755 permissions.

## Create fossasia rclone

```
mkdir -p ~/.config/rclone
```
create `.config/rclone/rclone.conf` with 0600 perm and the following content,
replacing `<ACCOUNT_ID>` and `<ACCOUNT_KEY>` with correct values.

Note that one can use a different `type` here, the outer `b2` is just a tag.
```
[b2]
type = b2
account = <ACCOUNT_ID>
key = <ACCOUNT_KEY>
```

## Create /var/log/fossasia 

```root@server
mkdir -p /var/log/fossasia
chown fossasia:fossasia /var/log/fossasia
```

## Create crontab for fossasia

**Edit** the `server-setup/crontab` according to the explanations there
(replace ENVFILE path and UUIDs for healthcheck) and install it as
crontab of user `fossasia`.



