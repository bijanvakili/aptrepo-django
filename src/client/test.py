#!/usr/bin/env python
"""
Sample REST API program
"""
import getpass
import json
import optparse
import sys
import api

class TestAppException(Exception):
    """ 
    Exceptions for the Test application 
    """
    
    message = "(Unknown error)"
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return self.message


class TestApp():
    """
    Simple test application
    """
    def __init__(self, baseurl, timeout, username=None, password=None, httpclient_type=None):
        self.apiclient = api.AptRepoClient(url=baseurl, 
                                           timeout=timeout, 
                                           httpclient_type=httpclient_type)
        self.username = username
        self.password = password
        
    def showrepo(self):
        """
        Display all contest in the apt repo
        """
        
        # output all distributions and sections
        distributions = self.apiclient.get_distribution_list()
        print 'Distributions:\n'
        for distribution in distributions:
            print json.dumps(distribution)
            print '\tSections:\n'
            sections = self.apiclient.list_sections(distribution['id'])
            print '\t' + json.dumps(sections)
            
            # output the default number of actions
            actions = self.apiclient.list_actions(distribution_id=distribution['id'])
            print 'Actions:\n'
            print json.dumps(actions, sort_keys=True, indent=4)
        
        
    def upload(self, distribution_name, section_name, package_filename):
        """
        Uploads a package to the repo
        
        distribution_name -- name or id of distribution
        section_name -- name or id of section
        package_filename -- filename of Debian .deb file to upload
        """
        self._authenticate()
        
        # determine the section IDs
        section_id = self._get_section_id(distribution_name, section_name)
        
        # upload the package
        self.apiclient.upload_package(section_id, filename=package_filename)
        
    def list(self, distribution_name, section_name):
        """
        Lists the contents of a repository
        
        distribution_name -- name or id of distribution
        section_name -- name or id of section
        """
        # determine the section IDs
        section_id = self._get_section_id(distribution_name, section_name)

        # retrieve and display all the package instances
        package_instances = self.apiclient.list_section_packages(section_id)
        print json.dumps(package_instances, sort_keys=True, indent=4)

    def remove(self, distribution_name, section_name, package_name, version, architecture):
        """
        Deletes a package instance from the repo
        
        distribution_name -- name or id of distribution
        section_name -- name or id of section
        package_name -- name of the Debian package
        version -- package version
        architecture -- architecture to remove
        """
        self._authenticate()
        
        # determine the section IDs
        section_id = self._get_section_id(distribution_name, section_name)

        # locate and remove the package instance
        package_instance = self.apiclient.get_package_instance(section_id=section_id, 
                                                               name=package_name, 
                                                               version=version, 
                                                               architecture=architecture)
        self.apiclient.delete_package_instance(package_instance['id'])
        
    def _get_section_id(self, distribution_name, section_name):
        """
        Internal method to retrieve the section ID
        
        distribution -- name or id of distribution
        section -- name or id of section
        """
        # determine the target distribution and section IDs
        distributions = self.apiclient.get_distribution_list()
        distributions = filter(lambda x: x['name'] == distribution_name, distributions)
        if len(distributions) < 1:
            raise TestAppException('Distribution not found: ' + distribution_name)
        distribution = distributions[0]
        
        sections = self.apiclient.list_sections(distribution['id'])
        sections = filter(lambda x: x['name'] == section_name, sections)
        if len(sections) < 1:
            raise TestAppException('Section not found: ' + section_name)
        return sections[0]['id'] 

    def _authenticate(self):
        """
        Ensures the client is authenticated
        """
        if self.apiclient.is_authenticated():
            return
        
        # default to the system username
        if not self.username:
            self.username = getpass.getuser()
            
        # prompt for a password if none was provided
        if not self.password:
            try:
                self.password = getpass.getpass()
            except getpass.GetPassWarning:
                pass
            
        if not self.username or not self.password:
            raise TestAppException('Username and password must be provided')
        
        self.apiclient.login(self.username, self.password)

def main(argv=None):
    """
    Main program
    
    argv -- list of CLI arguments
    """
    # parse the options
    parser = optparse.OptionParser()
    usage_commands = [
        'showrepo',
        'list <distribution> <section>',
        'upload <distribution> <section> <package.deb>',
        'remove <distribution> <section> <package> <version> <architecture>']
    usage_commands = map( lambda x: '%prog [options] ' + x, usage_commands)
    parser.set_usage('\n\t' + '\n\t'.join(usage_commands))
    parser.add_option('--baseurl', action='store', 
                      type='string', dest='baseurl', 
                      help='Base URL to repository',
                      default="http://localhost:8000/aptrepo/api")
    parser.add_option('--timeout', action='store',
                      type='int', dest='timeout', 
                      help='Network timeout',
                      default=60)
    parser.add_option('--username', action='store',
                      type='string', dest='username',
                      help='Username')
    parser.add_option('--password', action='store',
                      type='string', dest='password',
                      help='Password')
    parser.add_option('--use-httpclient', action='store',
                      type='string', dest='httpclient_type',
                      help=optparse.SUPPRESS_HELP)
    (options, args) = parser.parse_args(args=argv)
    
    if len(args) < 1:
        parser.print_help()
        sys.exit(0)

    method_name = args.pop(0)
    app = TestApp(**options.__dict__)
    if not (hasattr(app, method_name) and callable(getattr(app, method_name))):
        raise TestAppException('Invalid command: ' + method_name)
    
    # execute the command
    getattr(app, method_name)(*args)


if __name__ == "__main__":
    try:
        main(argv=sys.argv[1:])
    except Exception as e:
        print >>sys.stderr, e
        sys.exit(1)
