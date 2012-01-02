# aptrepo2 build script

all: build

DJANGO_ADMINCMD=\
	APTREPO_ROOT=`pwd` python src/server/manage.py
DJANGO_TESTSERVER_ADDRESS=0.0.0.0:8000
BUILD_DIR=.build

SRC_IMAGES_DIR=share/images

ALL_IMAGES = \
	$(patsubst %.svg, $(BUILD_DIR)/%.png, \
		$(shell find $(SRC_IMAGES_DIR) -name \*.svg -print)	\
	) 

# Construct directory hierarchy for build directory
dirs:
	mkdir -p $(BUILD_DIR)/locale
	mkdir -p $(BUILD_DIR)/share/images 

# Common rule to convert scalable (.svg) images to raster images (.png)
$(BUILD_DIR)/share/images/%.png: share/images/%.svg dirs
	convert -resize 16x16 -background none $< $@ 

build-images: $(ALL_IMAGES)
	
build:
	@echo "Localizing strings..."
	$(DJANGO_ADMINCMD) makemessages -a
	$(DJANGO_ADMINCMD) compilemessages
	@echo "Done"  

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


.PHONY: clean-testenv db-init test build build-images dirs
