#!/bin/sh

echo "============== waiting for postgres ================="

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

echo "============== postgresql is ready =================="

# Since static.dist is mounted as shared volume, we need to move over
# the files from static.dist.backup to static.dist
echo "============== moving files from static.dist.backup to static.dist ==="
# mind the final dash after backup/ so that only the content is transfered!!!
rync -avz --delete /home/app/web/eventyay/static.dist.backup/ /home/app/web/eventyay/static.dist
#echo "============== compiling translation messages ================"
#python manage.py compilemessages
#echo "============== compiling JS translation messages ================"
#python manage.py compilejsi18n
#echo "============== running collectstatic ================"
#python manage.py collectstatic --noinput
echo "============== running compress ====================="
python manage.py compress
echo "============== running migrate ======================"
python manage.py migrate
echo "============== starting application ================="
exec "$@"
