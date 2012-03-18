# aptrepo2 build script

all: build

DJANGO_ADMINCMD=\
	APTREPO_ROOT=`pwd` python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000
BUILD_DIR=.build

SRC_IMAGES_DIR=share/images
DEST_IMAGES_DIR=var/public/images
IMAGE_CONVERT=python src/build/images.py

TEST_DATABASE=var/db/aptrepo.db

# Construct directory hierarchy for build directory
dirs:
	mkdir -p $(BUILD_DIR)/locale
	mkdir -p $(DEST_IMAGES_DIR) 

# Convert any vector graphics to raster images
convert-images: dirs
	$(IMAGE_CONVERT) $(SRC_IMAGES_DIR) $(DEST_IMAGES_DIR)

# Localize strings using django gettext
localize:
	$(DJANGO_ADMINCMD) makemessages -a
	$(DJANGO_ADMINCMD) compilemessages
	
build: convert-images localize
	mkdir -p var/public/css
	cp -R share/css var/public/.

clean:
	@echo "Removing test files..."
	rm -rf var/db/aptrepo.db var/cache/* $(DEST_IMAGES_DIR) var/public/css
	@echo "Removing build directory..."
	rm -rf $(BUILD_DIR)
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


.PHONY: clean unittest testserver build convert-images localize dirs dbinit
