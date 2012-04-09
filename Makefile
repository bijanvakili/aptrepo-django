# aptrepo2 build script

all: build

DJANGO_ADMINCMD=\
	APTREPO_ROOT=`pwd` python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000
BUILD_DIR=.build

SRC_IMAGES_DIR=share/media/images/source
DEST_IMAGES_DIR=share/media/images/raster
IMAGE_CONVERTER=python src/build/images.py --srcdir=$(SRC_IMAGES_DIR) --destdir=$(DEST_IMAGES_DIR)
IMAGE_MANIFEST=$(SRC_IMAGES_DIR)/image_manifest.json

TEST_DATABASE=var/db/aptrepo.db

# Convert any vector graphics to raster images
SOURCE_IMAGES=$(shell $(IMAGE_CONVERTER) sources)
OUTPUT_IMAGES=$(shell $(IMAGE_CONVERTER) destfiles)

$(OUTPUT_IMAGES): $(SOURCE_IMAGES) $(IMAGE_MANIFEST)
	mkdir -p $(DEST_IMAGES_DIR)
	$(IMAGE_CONVERTER) build $(SRC_IMAGES_DIR) $(DEST_IMAGES_DIR)
 
images: $(OUTPUT_IMAGES)

# Localize strings using django gettext
L10N_SOURCES=$(shell find src/server/ share/ \( -name \*.py -o -name \*.html \) -print)
L10N_MESSAGES=$(shell find locale/ -name \*.po -print)
L10N_BINARIES=$(patsubst %.po, %.mo, $(L10N_MESSAGES)) 

$(L10N_BINARIES): $(L10N_SOURCES) $(L10N_MESSAGES)
	$(DJANGO_ADMINCMD) makemessages -a 
	$(DJANGO_ADMINCMD) compilemessages

localize: $(L10N_BINARIES)
	
build: images localize

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


.PHONY: clean unittest testserver build images localize dbinit todos
