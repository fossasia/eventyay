all: localecompile staticfiles
production: localecompile staticfiles compress
LNGS := $(foreach d,$(shell find eventyay/locale -mindepth 1 -maxdepth 1 -type d),-l $(notdir $(d)))

localecompile:
	./manage.py compilemessages --ignore ".venv"

localegen:
	./manage.py makemessages --keep-pot --ignore "eventyay/helpers/*" --ignore "eventyay/webapp/*" $(LNGS)
	./manage.py makemessages --keep-pot -d djangojs --ignore "eventyay/helpers/*" --ignore "eventyay/static/jsi18n/*" --ignore "eventyay/static.dist/*" --ignore "data/*" --ignore "eventyay/static/rrule/*" --ignore "build/*" --ignore "eventyay/webapp/*" --ignore "*/node_modules/*" --ignore "*/dist/*" $(LNGS)
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
