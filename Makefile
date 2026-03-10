all: localecompile staticfiles
production: localecompile staticfiles compress
LNGS:=`find src/eventyay/locale/ -mindepth 1 -maxdepth 1 -type d -printf "-l %f "`

localecompile:
	./manage.py compilemessages

localegen:
	./manage.py makemessages --keep-pot --ignore "src/eventyay/helpers/*" $(LNGS)
	./manage.py makemessages --keep-pot -d djangojs --ignore "src/eventyay/helpers/*" --ignore "src/eventyay/static/jsi18n/*" --ignore "src/eventyay/static/jsi18n/*" --ignore "src/eventyay/static.dist/*" --ignore "data/*" --ignore "src/eventyay/static/rrule/*" --ignore "build/*" $(LNGS)

staticfiles: jsi18n
	./manage.py collectstatic --noinput

compress: npminstall
	./manage.py compress

jsi18n: localecompile
	./manage.py compilejsi18n

test:
	pytest tests

coverage:
	coverage run -m pytest

npminstall:
	# keep this in sync with setup.py!
	npm ci --prefix=webapps/schedule-editor
	npm ci --prefix=webapps/schedule
	OUT_DIR=$(shell pwd)/data/compiled-frontend/ npm run build --prefix=webapps/schedule-editor
	OUT_DIR=$(shell pwd)/data/compiled-frontend/ npm run build:wc --prefix=webapps/schedule
	npm ci --prefix=webapps/webcheckin
	OUT_DIR=$(shell pwd)/data/compiled-frontend/ npm run build --prefix=webapps/webcheckin
	npm ci --prefix=webapps/video
	OUT_DIR=$(shell pwd)/data/compiled-frontend/ npm run build --prefix=webapps/video
