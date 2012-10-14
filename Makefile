# aptrepo2 build script

all: build

DJANGO_ADMINCMD=\
	APTREPO_ROOT=`pwd` python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000
BUILD_DIR=.build
TOOLS_ROOT_DIR=tools
TOOLS_BIN_DIR=$(TOOLS_ROOT_DIR)/bin

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
L10N_SOURCES=$(shell find src/server/ share/ \( -name \*.py -o -name \*.html -o -name \*.js \) -print)
L10N_MESSAGES=$(shell find locale/ -name \*.po -print)
L10N_BINARIES=$(patsubst %.po, %.mo, $(L10N_MESSAGES)) 

$(L10N_BINARIES): $(L10N_SOURCES) $(L10N_MESSAGES)
	$(DJANGO_ADMINCMD) makemessages -a -d django 
	$(DJANGO_ADMINCMD) makemessages -a -d djangojs
	$(DJANGO_ADMINCMD) compilemessages

localize: $(L10N_BINARIES)

SRC_JAVASCRIPT_DIR=share/media/js
JAVASRIPT_SOURCES=$(shell find $(SRC_JAVASCRIPT_DIR) -maxdepth 1 -name \*.js -print)

analyze-js: $(JAVASRIPT_SOURCES)
	$(TOOLS_BIN_DIR)/jslint --jslint-home=$(TOOLS_ROOT_DIR) $(JAVASRIPT_SOURCES)

SRC_PYTHON_DIR=./src
SRC_PYTHON_MODULES=`ls src`
analyze-py:
	PYTHONPATH=src pylint --rcfile=tools/etc/pylint.rc $(SRC_PYTHON_MODULES)  

analyze: analyze-js analyze-py

build: images localize

clean:
	@echo "Removing test files..."
	rm -rf $(TEST_DATABASE) var/cache/* $(DEST_IMAGES_DIR)
	@echo "Removing all compiled python modules from the source hierarchy..."
	find "$(SRC_PYTHON_DIR)" -name \*.pyc -exec rm -rf '{}' \;
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
	$(DJANGO_ADMINCMD) runserver --insecure $(DJANGO_TESTSERVER_ADDRESS)

	
# Output TODO items from source code
todos:
	@grep -nR TODO src/* share/* test/* | grep -v ^$(SRC_JAVASCRIPT_DIR)/lib


.PHONY: clean unittest testserver build images localize dbinit todos
.PHONY: analyze analyze-js analyze-py
