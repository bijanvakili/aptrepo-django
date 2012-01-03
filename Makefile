# aptrepo2 build script

all: build

DJANGO_ADMINCMD=\
	APTREPO_ROOT=`pwd` python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000
BUILD_DIR=.build

SRC_IMAGES_DIR=share/images
DEST_IMAGES_DIR=$(BUILD_DIR)/$(SRC_IMAGES_DIR)
IMAGE_CONVERT=python src/build/images.py

# Construct directory hierarchy for build directory
dirs:
	mkdir -p $(BUILD_DIR)/locale
	mkdir -p $(BUILD_DIR)/share/images 

# Convert any vector graphics to raster images
convert-images: dirs
	$(IMAGE_CONVERT) $(SRC_IMAGES_DIR) $(DEST_IMAGES_DIR)

# Localize strings using django gettext
localize:
	$(DJANGO_ADMINCMD) makemessages -a
	$(DJANGO_ADMINCMD) compilemessages
	
build: convert-images localize

clean:
	@echo "Removing build directory..."
	rm -rf $(BUILD_DIR)
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


.PHONY: clean-testenv db-init test build convert-images localize dirs
