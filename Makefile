# aptrepo2 build script

all: build

DJANGO_ADMINCMD=python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000


build:
	@echo "Localizing strings..."
	$(DJANGO_ADMINCMD) makemessages -a
	$(DJANGO_ADMINCMD) compilemessages
	@echo "Done"  


clean:
	@echo "Removing all binary l10n catalogs from the locale hierarchy..."
	find . -name \*.mo -exec rm -rf '{}' \;
	@echo "Done"


# Removes the repository and associated content
clean-testenv:
	rm -rf var/db/aptrepo.db var/cache/*

	
# Initializes the aptrepo database to a useable state
db-init: clean-testenv
	$(DJANGO_ADMINCMD) syncdb --noinput
	$(DJANGO_ADMINCMD) loaddata simple_repository


# Runs the unit tests
unittest:
	$(DJANGO_ADMINCMD) test aptrepo


# Runs the local test server (allows outside access)
testserver:
	$(DJANGO_ADMINCMD) runserver $(DJANGO_TESTSERVER_ADDRESS)

	
# Output TODO items from source code
todos:
	@grep -R TODO src/* share/* test/*


.PHONY: clean-testenv db-init test build
