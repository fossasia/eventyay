# Creating a new server and deployment

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
apt install nginx ssl-cert certbot
```

## Switch to user fossasia

```fossasia@server
DEPLOYMENT=<NAME_OF_THE_DEPLOYMENT>
cd /home/fossasia/$DEPLOYMENT
git clone https://github.com/fossasia/eventyay.git
cd eventyay
git checkout main
ln -s eventyay/deployment/docker-compose.yaml .
```

Create .env
- change SERVER_NAME and CHANGEME entries

Copy eventyay/deployment/nginx/enext-direct to /etc/nginx/sites-available
ssl update
    apt install python3-certbot-nginx certbot
    certbot -m eventyay-devops@fossasia.org --agree-tos --nginx
