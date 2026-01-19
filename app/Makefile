all: localecompile staticfiles
production: localecompile staticfiles compress
LNGS:=`find eventyay/locale/ -mindepth 1 -maxdepth 1 -type d -printf "-l %f "`

localecompile:
	./manage.py compilemessages

localegen:
	./manage.py makemessages --keep-pot --ignore "eventyay/helpers/*" $(LNGS)
	./manage.py makemessages --keep-pot -d djangojs --ignore "eventyay/helpers/*" --ignore "eventyay/static/jsi18n/*" --ignore "eventyay/static/jsi18n/*" --ignore "eventyay/static.dist/*" --ignore "data/*" --ignore "eventyay/static/rrule/*" --ignore "build/*" $(LNGS)

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
	npm ci --prefix=eventyay/frontend/schedule-editor
	npm ci --prefix=eventyay/frontend/schedule
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/frontend/schedule-editor
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build:wc --prefix=eventyay/frontend/schedule
	npm ci --prefix=eventyay/frontend/webcheckin
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/frontend/webcheckin

webappbuild:
	npm ci --prefix=eventyay/webapp
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/webapp
