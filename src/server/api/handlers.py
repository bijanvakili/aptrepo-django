from django.core.exceptions import ObjectDoesNotExist
from piston.utils import rc
from piston.handler import BaseHandler
import server.aptrepo.models
from server.aptrepo.repository import Repository


class BaseAptRepoHandler(BaseHandler):
    """
    Abstract base class for all REST API handlers
    """
    
    def _find_distribution(self, distribution_id):
        """
        Searches for a distribution, first by the primary key and then by the name
        """
        distribution_model = server.aptrepo.models.Distribution
        distributions = distribution_model.objects.filter(id=distribution_id)
        if distributions.count() == 0:
            distributions = distribution_model.objects.filter(name=distribution_id)
        
        if distributions.count() == 0:
            raise ObjectDoesNotExist
        
    def _find_section(self, distribution_id, section_id):
        """
        Searches for a section, first by primary key and then by the name
        """
        section_model = server.aptrepo.models.Section
        if distribution_id:
            distribution = self._find_distribution(distribution_id)
            sections = section_model.objects.filter(id=section_id, distribution=distribution)
            if sections.count() == 0:
                sections = section_model.objects.filter(name=section_id, distribution=distribution)
        else:
            sections = section_model.objects.filter(id=section_id)
            
        if sections.count() == 0:
            raise ObjectDoesNotExist

    def _find_package_instance(self, distribution_id, section_id, 
                               instance_id=None, 
                               package_name=None, version=None, architecture=None):
        """
        Searches for a package instance by unique ID or the (name, version, architecture) tuple
        """
        if instance_id:
            return self.model.objects.get(id=instance_id)
        else:
            section  = self._find_section(distribution_id, section_id)
            return self.model.objects.get(section=section,
                                     package__name=package_name,
                                     package__version=version,
                                     package__architecture=architecture)


class PackageHandler(BaseAptRepoHandler):
    """
    REST API call handler for packages
    """
    allowed_methods = ('GET', 'DELETE')
    model = server.aptrepo.models.Package
    
    def read(self, request, id=None, name=None, version=None, architecture=None):
        return self._find_package(id, name, version, architecture)

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
            return self.models.objects.get(id)
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
                return self._find_distribution(distribution_id)
            
            except ObjectDoesNotExist:
                resp = rc.NOT_FOUND
                resp.write('Distribution not found: ' + id)
                return resp
        else:
            return self.model.objects.all()


class SectionHandler(BaseAptRepoHandler):
    """
    REST API call handler for sections
    """
    allowed_methods=('GET')
    model = server.aptrepo.models.Section

    def read(self, request, distribution_id=None, section_id=None):
        if section_id:
            try:
                return self._find_section(distribution_id, section_id)
            except ObjectDoesNotExist:
                resp = rc.NOT_FOUND
                resp.write('Distribution not found:  ({0}:{1})'.format(
                    distribution_id, section_id))
                return resp
        else:
            if distribution_id:
                distribution = self._find_distribution(distribution_id)
                return self.model.objects.filter(distribution=distribution)
            else:
                return self.model.objects.all()


class PackageInstanceHandler(BaseAptRepoHandler):
    """
    REST API call handler for package instances
    """
    allowed_methods=('GET', 'DELETE', 'POST')
    model = server.aptrepo.models.PackageInstance
    
    def read(self, request, distribution_id, section_id, 
             instance_id=None, 
             package_name=None, version=None, architecture=None):
        
        try:
            return self._find_package_instance(distribution_id, section_id, 
                                               instance_id, 
                                               package_name, version, architecture)
        except ObjectDoesNotExist:
            resp = rc.NOT_FOUND
            resp.write('Package not found in section: ({0}:{1})'.format(
                distribution_id, section_id))
            return resp
                            
    def delete(self, request, distribution_id, section_id, 
               instance_id=None, 
               package_name=None, version=None, architecture=None):
        try:
            package_instance=self._find_package_instance(distribution_id, section_id, 
                                                         instance_id, 
                                                         package_name, version, architecture)
            repository = Repository()
            repository.remove_package(package_instance.id)
            return rc.DELETED
        
        except ObjectDoesNotExist:
            return rc.NOT_FOUND

    def create(self, request, distribution_id, section_id):
        # if a file was uploaded, let the repository handle the file
        repository = Repository()
        section = self._find_section(distribution_id, section_id)
        new_instance_id = None
        if request.FILES['file']:
            uploaded_file = request.FILES['file']
            new_instance_id = repository.add_package(section.distribution.name, 
                                                   section.name, 
                                                   uploaded_file)
        # otherwise, clone based of the source package or instance ID
        elif request.content_type:
            clone_args = {'dest_distribution_name' : section.distribution.name,
                          'dest_section_name' : section.name }
            if request.data['source_id']:
                clone_args['instance_id'] = request.data['instance_id']
            elif request.data['package_id']:
                clone_args['package_id'] = request.data['package_id']
            new_instance_id = repository.clone_package(**clone_args)

        return {'new_instance_id' : new_instance_id}


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
            section = self._find_section(distribution_id, section_id)
            action_query['section_id'] = section.id

        # retrieve all actions for a distribution
        elif distribution_id:
            distribution = self._find_distribution(distribution_id)
            action_query['distribution_id'] = distribution.id
            
        repository=Repository()
        return repository.get_actions(*action_query)
