from django.core.exceptions import ObjectDoesNotExist
from piston.utils import rc, HttpStatusCode
from piston.handler import BaseHandler

import server.settings
import server.aptrepo.models
from server.aptrepo.repository import Repository
from server.aptrepo.common import AptRepoException

class BaseAptRepoHandler(BaseHandler):
    """
    Abstract base class for all REST API handlers
    """
    exclude = ()

    def _error_response(self, exception=None, return_code=None):
        """ 
        Return an error response 
        """
        response = rc.BAD_REQUEST
        response.content = str(exception)
        if return_code:
            rc.status_code = return_code
        
        if server.settings.DEBUG:
            raise HttpStatusCode(response)
        else:
            return response

class PackageHandler(BaseAptRepoHandler):
    """
    REST API call handler for packages
    """
    allowed_methods = ('GET', 'DELETE')
    model = server.aptrepo.models.Package
    
    def read(self, request, id=None, package_name=None, version=None, architecture=None):
        try:
            return self._find_package(id, package_name, version, architecture)
        except ObjectDoesNotExist:
            return rc.NOT_FOUND

    def delete(self, request, id=None, name=None, version=None, architecture=None):
        try:
            package = self._find_package(id, name, version, architecture)
            repository = Repository()
            repository.remove_all_package_instances(package.id)
            return rc.DELETED
        
        except ObjectDoesNotExist:
            return rc.NOT_FOUND
        
    def _find_package(self, id=None, name=None, version=None, architecture=None):
        if id:
            return self.models.objects.get(id=id)
        elif name and version and architecture:
            return self.models.objects.get(package_name=name, version=version, 
                                           architecture=architecture)
        
class DistributionHandler(BaseAptRepoHandler):
    """
    REST API call handler for distributions
    """
    allowed_methods=('GET')
    model = server.aptrepo.models.Distribution
    
    def read(self, request, distribution_id=None):
        if distribution_id:
            try:
                return self.model.objects.get(id=distribution_id)
            except ObjectDoesNotExist:
                return rc.NOT_FOUND
        else:
            return self.model.objects.all()


class SectionHandler(BaseAptRepoHandler):
    """
    REST API call handler for sections
    """
    allowed_methods=('GET')
    model = server.aptrepo.models.Section

    def read(self, request, distribution_id=None, section_id=None):
        # return a specific section
        if section_id:
            try:
                return self.model.objects.get(id=section_id)
            except ObjectDoesNotExist:
                resp = rc.NOT_FOUND
                resp.write('Section not found: {0}'.format(section_id))
                return resp
            
        # return all sections within a distribution
        elif distribution_id:
            try:
                return self.model.objects.filter(distribution__id=distribution_id)
            except ObjectDoesNotExist:
                resp = rc.NOT_FOUND
                resp.write('Distribution not found: ' + distribution_id)
                return resp
        
        # return all available sections
        else:
            return self.model.objects.all()


class PackageInstanceHandler(BaseAptRepoHandler):
    """
    REST API call handler for package instances
    """
    allowed_methods=('GET', 'DELETE', 'POST')
    model = server.aptrepo.models.PackageInstance
    fields = ('id', 'package', 'creator', 'creation_date')
    
    def read(self, request, instance_id=None, section_id=None, 
             package_name=None, version=None, architecture=None):
        
        # search for a specific instance
        if instance_id or (section_id and package_name and version and architecture):
            try:
                return self._find_package_instance(instance_id, section_id, 
                                                   package_name, version, architecture)
            except ObjectDoesNotExist:
                resp = rc.NOT_FOUND
                if instance_id:
                    resp.content = 'Package instance not found: {0}'.format(instance_id)
                else:
                    resp.content = 'Package instance not found in section {0} '\
                                    'matching criteria: ({1},{2},{3})'.format(section_id, 
                                                                         package_name, 
                                                                         version,
                                                                         architecture) 
                return resp
            
        # return all packages in a section
        elif section_id:
            return self.model.objects.filter(section__id=section_id)
        # show that displaying all package instances in the entire repository
        # is disallowed
        else:
            return rc.FORBIDDEN      
            
                            
    def delete(self, request, instance_id=None, section_id=None, 
               package_name=None, version=None, architecture=None):
        # delete a specific instance
        if instance_id or (section_id and package_name and version and architecture):
            try:
                package_instance=self._find_package_instance(instance_id, section_id, 
                                                             package_name, version, architecture)
                repository = Repository()
                repository.remove_package(package_instance.id)
                return rc.DELETED
            
            except ObjectDoesNotExist:
                return rc.NOT_FOUND
            except AptRepoException, e:
                return self._error_response(e)
        else:
            return rc.FORBIDDEN      

    def create(self, request, section_id):
        
        try:
            if not section_id:
                raise AptRepoException('No repository section specified')
            
            # if a file was uploaded, let the repository handle the file
            repository = Repository()
            section = server.aptrepo.models.Section.objects.get(id=section_id)
            new_instance_id = None
            if request.FILES['file']:
                uploaded_file = request.FILES['file']
                new_instance_id = repository.add_package(section.distribution.name, 
                                                         section.name, 
                                                         uploaded_file)
            # otherwise, clone based of the source package or instance ID
            else:
                clone_args = {'dest_distribution_name' : section.distribution.name,
                              'dest_section_name' : section.name }
                if request.data['source_id']:
                    clone_args['instance_id'] = request.data['instance_id']
                elif request.data['package_id']:
                    clone_args['package_id'] = request.data['package_id']
                new_instance_id = repository.clone_package(**clone_args)
    
            return self.model.objects.get(id=new_instance_id)
        
        except AptRepoException, e:
            return self._error_response(e)

    def _find_package_instance(self, instance_id=None, 
                               section_id=None, package_name=None, 
                               version=None, architecture=None):
        """
        Searches for a package instance by unique ID or the (name, version, architecture) tuple
        """
        if instance_id:
            return self.model.objects.get(id=instance_id)
        else:
            return self.model.objects.get(section__id=section_id,
                                          package__package_name=package_name,
                                          package__version=version,
                                          package__architecture=architecture)


class ActionHandler(BaseAptRepoHandler):
    """
    REST API call handler for querying actions
    """
    allowed_methods=('GET')
    model = server.aptrepo.models.Action
    
    def read(self, request, distribution_id=None, section_id=None):
        
        # add restriction parameters
        action_query = {}
        for k in ('min_timestamp', 'max_timestamp', 'max_items'):
            if k in request.GET:
                action_query[k] = request.GET[k]
        
        # retrieve all actions for a section
        if section_id:
            action_query['section_id'] = section_id

        # retrieve all actions for a distribution
        elif distribution_id:
            action_query['distribution_id'] = distribution_id
            
        repository=Repository()
        try:
            return repository.get_actions(**action_query)
        except ObjectDoesNotExist:
            return rc.NOT_FOUND
        
