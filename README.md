# aptrepo

## Automated Deployment (using Vagrant)

Automated deployment requires the following to be installed:

1. [VirtualBox](https://www.virtualbox.org/)
2. [Vagrant](https://www.vagrantup.com/)

### Steps

From the root aptrepo folder run the following:

	vagrant up
	vagrant ssh
	
Upon logging into your VM, run the following:

	source /opt/aptrepo_pyenv/bin/activate
    cd /vagrant

Your now ready to run the apt repo server (see below).
  
## Manual Deployment

Install the necessary Debian packages for build time dependencies:

    sudo apt-get install make gettext librsvg2-bin rhino pylint sqlite3

Install the necessary Debian packages for runtime dependencies:

    sudo apt-get install python-virtualenv python-pip python-apt python-debian python-pyme
    sudo mkdir /opt
	sudo virtualenv --system-site-packages /opt/aptrepo_pyenv
	source /opt/aptrepo_pyenv/bin/activate
	pip install -r tools/share/python/requirements.txt
	
## Building

    make build

## Running the server

Run the following commands:

	make testserver

Then open the following in your web browser: [http://localhost:8000/aptrepo/web/](http://localhost:8000/aptrepo/web/)

## Running the tests

	make unittest

## Notes

This has only been tested on Ubuntu 14.04 LTS
