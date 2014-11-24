#!/bin/bash

set -e

# install r10k
gem install r10k

# install required puppet modules using r10k
VAGRANT_ROOT="/vagrant"
export PUPPETFILE="$VAGRANT_ROOT/tools/share/puppet/Puppetfile"
export PUPPETFILE_DIR="$VAGRANT_ROOT/tools/share/puppet/modules"
r10k puppetfile install

# ensure apt repositories are up to date before running puppet
apt-get update
