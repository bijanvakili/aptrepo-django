from functools import wraps
import logging
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ObjectDoesNotExist
from piston.utils import rc, HttpStatusCode
from piston.handler import BaseHandler
from django.conf import settings
import server.aptrepo.models
from server.aptrepo.views import get_repository_controller
from server.aptrepo.util import AptRepoException, AuthorizationException

def handle_exception(request_handler_func):
    """
    Decorator function for handling exceptions and converting them
    to the appropriate response for the API client
    """
    @wraps(request_handler_func)
    def wrapper_handler(*args, **kwargs):
        logger = logging.getLogger(server.settings.DEFAULT_LOGGER)

        try:
            return request_handler_func(*args, **kwargs)
        except ObjectDoesNotExist:
            return rc.NOT_FOUND
        except AuthorizationException as e:
            logger.info(e)
            response = rc.FORBIDDEN
            response.content = str(e)
            return response
        except Exception as e:
            logger.exception(e)
            response = rc.BAD_REQUEST
            response.content = str(e)
            if server.settings.DEBUG:
                raise HttpStatusCode(response)
            else:
                return response
    
    return wrapper_handler

class BaseAptRepoHandler(BaseHandler):
    """
    Abstract base class for all REST API handlers
    """
    exclude = ()

    def _constrain_queryset(self, request, db_result, default_limit):
        """
        Constrain a DB query result based on common HTTP parameters:
        
        offset -- Start of the range (defaults to 0)
        limit -- Maximum number of items to return (defaults to 'default_limit')
        descending -- Should the results should be in reverse order (defaults to False)
        """
        min = 0
        if 'offset' in request.GET:
            min = int(request.GET['offset']) 
        
        max = default_limit
        if 'limit' in request.GET:
            max = min + int(request.GET['limit'])
        
        resultset = db_result[min:max]
        if 'descending' in request.GET and request.GET['descending']:
            resultset = resultset.reverse()
            
        return resultset

class SessionHandler(BaseAptRepoHandler):
    """
    REST API call handler for creating authenticated sessions
    """
    allowed_methods = ('POST', 'DELETE')
    
    @handle_exception
    def create(self, request):
        """
        Creates a session (logs in a client)
        """
        # check preconditions
        if 'username' not in request.POST or 'password' not in request.POST:
            raise AptRepoException("'username' and 'password' must be specified")
    
        # authenticate the user and retrieve the session token
        user = authenticate(username=request.POST['username'],
                            password=request.POST['password'])
        if not user or not user.is_active:
            response = rc.BAD_REQUEST
            response.content = 'Invalid username or password'
            return response
        
        login(request, user)
        return request.session.session_key
            
    @handle_exception
    def delete(self, request, session_key):
        """
        Deletes a session (logs a user out)
        """
        if request.session.session_key == session_key:
            logout(request)
            return rc.DELETED
        else:
            session_backend = __import__(settings.SESSION_ENGINE)
            session_db =  session_backend.SessionStore()
            session_db.delete(session_key)
            return rc.DELETED
        return rc.NOT_FOUND


class PackageHandler(BaseAptRepoHandler):
    """
    REST API call handler for packages
    """
    allowed_methods = ('GET', 'DELETE')
    model = server.aptrepo.models.Package
    _DEFAULT_MAX_PACKAGES = 100
    
    @handle_exception
    def read(self, request, **kwargs):
        # if no arguments were specified, return all package
        if (len(kwargs) == 0):
            return self._constrain_queryset(request, self.model.objects.all(), 
                                            self._DEFAULT_MAX_PACKAGES)
        
        # otherwise, search for a specific package
        return self._find_package(**kwargs)

    @handle_exception
    def delete(self, request, **kwargs):
        package = self._find_package(**kwargs)
        repository = get_repository_controller(request=request)
        repository.remove_all_package_instances(package.id)
        return rc.DELETED
        
    def _find_package(self, id=None, package_name=None, version=None, architecture=None):
        if id:
            return self.model.objects.get(id=id)
        elif package_name and version and architecture:
            return self.model.objects.get(package_name=package_name, version=version, 
                                           architecture=architecture)
        
class DistributionHandler(BaseAptRepoHandler):
    """
    REST API call handler for distributions
    """
    allowed_methods=('GET')
    model = server.aptrepo.models.Distribution

    @handle_exception
    def read(self, request, distribution_id=None):
        if distribution_id:
            return self.model.objects.get(id=distribution_id)
        else:
            return self.model.objects.all()


class SectionHandler(BaseAptRepoHandler):
    """
    REST API call handler for sections
    """
    allowed_methods=('GET')
    model = server.aptrepo.models.Section
    exclude = ('distribution',)

    @handle_exception
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
    
    _DEFAULT_MAX_INSTANCES = 100
    
    @handle_exception
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
            
        # return all packages in a section (within constrained limits)
        elif section_id:
            section_instances = self.model.objects.filter(section__id=section_id) 
            return self._constrain_queryset(request, section_instances, self._DEFAULT_MAX_INSTANCES) 
        
        # display all package instances (within constrained limits)
        else:
            all_instances = self.model.objects.all()
            return self._constrain_queryset(request, all_instances, 
                                            default_limit=self._DEFAULT_MAX_INSTANCES)
            
    @handle_exception
    def delete(self, request, instance_id=None, section_id=None, 
               package_name=None, version=None, architecture=None):
        # delete a specific instance
        if instance_id or (section_id and package_name and version and architecture):
            package_instance=self._find_package_instance(instance_id, section_id, 
                                                         package_name, version, architecture)
            repository = get_repository_controller(request=request)
            repository.remove_package(package_instance.id)
            return rc.DELETED
        else:
            return rc.FORBIDDEN      

    @handle_exception
    def create(self, request, section_id):
        
        if not section_id:
            raise AptRepoException('No repository section specified')
        
        # if a file was uploaded, let the repository handle the file
        repository = get_repository_controller(request=request)
        section = server.aptrepo.models.Section.objects.get(id=section_id)
        new_instance_id = None
        comment = request.POST.get('comment')
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            new_instance_id = repository.add_package(section=section, 
                                                     uploaded_package_file=uploaded_file,
                                                     comment=comment)
        # otherwise, clone based of the source package or instance ID
        else:
            clone_args = {'dest_section' : section, 'comment':comment }
            if 'source_id' in request.POST:
                clone_args['instance_id'] = request.POST['instance_id']
            elif 'package_id' in request.POST:
                clone_args['package_id'] = request.POST['package_id']
            else:
                return rc.BAD_REQUEST
            new_instance_id = repository.clone_package(**clone_args)

        return self.model.objects.get(id=new_instance_id)

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
    
    _DEFAULT_NUM_ACTIONS = 25
    
    @handle_exception
    def read(self, request, distribution_id=None, section_id=None):
        
        # add restriction parameters
        action_query = {}
        for k in ('min_ts', 'max_ts'):
            if k in request.GET:
                action_query[k] = request.GET[k]
        
        # retrieve all actions for a section
        if section_id:
            action_query['section_id'] = section_id

        # retrieve all actions for a distribution
        elif distribution_id:
            action_query['distribution_id'] = distribution_id
            
        repository=get_repository_controller(request=request)
        action_results = repository.get_actions(**action_query)
        return self._constrain_queryset(request, action_results, 
                                        default_limit=self._DEFAULT_NUM_ACTIONS)
