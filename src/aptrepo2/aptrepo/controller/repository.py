
import aptrepo2.aptrepo.models

# TODO enforce exclusive access for all write operations

class Repository:
    """
    Manages the apt repository including all packages and associated metadata
    """
    
    def add_package(self, distribution, section, package_file):
        """
        Add a package to the repository
        """
        # check preconditions
        
        # compute the package hashes

        # check if the package already exists in the UniqueFile table
        # if the package already exists
        #    get the file id
        # else
        #    compute the new filename
        #    save the file in the store
        #    create a new UniqueFile instance
        # end if
        
        # extract the 'control' information
        # if the architecture is not valid for this distribution
        #    fail with an error
        # end if
        # if a matching file does not already exist
        #    if (package, architecture, version) already exists
        #        fail with an error
        #    end if
        #    create a new package entry
        # end if
        
        # check the instances table
        # if the package id doesn't already exist
        #    create a new instance
        # end if
        
        # update repo metadata(distribution, section, architecture)
        
        # insert action 
        
        pass
        
    def remove_package(self, distribution, section, package_name, architecture, version):
        # TODO
        pass
    
    def _update_metadata(self, recreate=False, **kwargs):
        """
        Update of repository metadata (recursive)
        
        force - Flag indicating whether to force data from scratch
        
        Optional keyword arguments include:
        distribution - Update only a single distribution
        section      - Update only a single section (distribution must be specified)
        architecture - Update only an architecture set (distribution and section must be specified) 
        """
        # if (distribution, section, architecture) are all specified
        #    _update_package_list for (distribution, section, architecture)
        # else if only (distribution, section) are specified
        #    if force then
        #        for each architecture in the section
        #            update package list for (distribution, section, architecture) 
        #        end for
        #    end if
        # end if
        # 
        # if distribution is specified
        #    if recreate then
        #        for each section
        #            for each architecture
        #                update package list for (distribution, section, architecture)
        #            end for
        #        end for
        #    else
        #    _update_releases for (distribution)
        # else
        #    for each distribution
        #        _update_metadata(recreate, distribution)
        #    end if
        # end if
        pass
    
    
    def _update_package_list(self, distribution, section, architecture):
        """
        Updates a Debian 'Packages' file for a subsection of the repository
        """
        #    for each package instance in (distribution, section, architecture)
        #        append package info to package data
        #    end for
        #    compute hash of dumped data
        #    compress and compute hash for Packages.gz
        #    save the files
        #    insert or update entry in UniqueFile entry for Packages and Packages.gz
        pass
    
    def _update_release_list(self, distribution):
        """
        Updates a Debian 'Releases' file for a single distribution
        """
        # create new release with standard data
        # for each entry in UniqueFile that is prefixed with the distribution
        #   add an md5sum entry
        #   add a SHA1 entry
        #   add a SHA256 entry
        # end for
        
        # save the Release file
        # GPG sign the release file
