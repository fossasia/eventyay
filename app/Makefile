all: localecompile staticfiles
production: localecompile staticfiles compress
# English is the gettext source language (*.pot). Passing -l en recreates
# locale/en/LC_MESSAGES/*.po, which Weblate reports as a duplicated source translation.
LNGS := $(foreach d,$(shell find eventyay/locale -mindepth 1 -maxdepth 1 -type d ! -name en),-l $(notdir $(d)))

localecompile:
	./manage.py compilemessages

localegen:
	./manage.py makemessages --keep-pot $(LNGS)
	./manage.py makemessages --keep-pot -d djangojs $(LNGS)
	npm run i18n:extract --prefix=eventyay/webapp/video
	npm run i18n:extract --prefix=eventyay/webapp/schedule
	npm run i18n:extract --prefix=eventyay/webapp/schedule-editor

staticfiles: jsi18n
	./manage.py collectstatic --noinput

compress: npminstall
	./manage.py compress --force

jsi18n: localecompile
	./manage.py compilejsi18n

test:
	pytest tests

coverage:
	coverage run -m pytest

npminstall:
	# keep this in sync with setup.py!
	npm ci --prefix=eventyay/webapp/schedule-editor
	npm ci --prefix=eventyay/webapp/schedule
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/webapp/schedule-editor
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/webapp/schedule
	npm ci --prefix=eventyay/webapp/video
	OUT_DIR=$(shell pwd)/eventyay/data/compiled-frontend/ npm run build --prefix=eventyay/webapp/video
