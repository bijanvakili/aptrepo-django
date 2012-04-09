# aptrepo2 build script

all: build

DJANGO_ADMINCMD=\
	APTREPO_ROOT=`pwd` python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000
BUILD_DIR=.build

SRC_IMAGES_DIR=share/media/images
DEST_IMAGES_DIR=share/media/images/raster
IMAGE_CONVERT=python src/build/images.py

TEST_DATABASE=var/db/aptrepo.db

# Convert any vector graphics to raster images
convert-images:
	mkdir -p $(DEST_IMAGES_DIR) 
	$(IMAGE_CONVERT) $(SRC_IMAGES_DIR) $(DEST_IMAGES_DIR)

# Localize strings using django gettext
localize:
	$(DJANGO_ADMINCMD) makemessages -a
	$(DJANGO_ADMINCMD) compilemessages
	
build: convert-images localize

clean:
	@echo "Removing test files..."
	rm -rf $(TEST_DATABASE) var/cache/* $(DEST_IMAGES_DIR)
	@echo "Removing all binary l10n catalogs from the locale hierarchy..."
	find . -name \*.mo -exec rm -rf '{}' \;
	@echo "Done"


# Initializes the aptrepo database to a useable state
$(TEST_DATABASE): 
	$(DJANGO_ADMINCMD) syncdb --noinput
	$(DJANGO_ADMINCMD) loaddata simple_repository

dbinit: $(TEST_DATABASE)

# Runs the unit tests
unittest:
	$(DJANGO_ADMINCMD) test aptrepo


# Runs the local test server (allows outside access)
testserver: build dbinit 
	$(DJANGO_ADMINCMD) runserver $(DJANGO_TESTSERVER_ADDRESS)

	
# Output TODO items from source code
todos:
	@grep -R TODO src/* share/* test/*


.PHONY: clean unittest testserver build convert-images localize dbinit
