import json
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
import django.contrib.auth.views
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from server.aptrepo import models
from server.aptrepo.util import constrain_queryset
from server.aptrepo.util.download import TemporaryDownloadedFile
from server.aptrepo.views import get_repository_controller
from server.aptrepo.views.decorators import handle_exception
from server.aptrepo.views.webpages import widgets

class UploadPackageForm(forms.Form):
    """
    Form class for package uploads
    """
    file = widgets.AdvancedFileField(label=_('Package File or URL'))
    comment = forms.CharField(label=_('Optional comment'),
                              required=False, 
                              max_length=models.Action.MAX_COMMENT_LENGTH)
    sections = forms.ModelMultipleChoiceField(label=_('Sections'),
                                              queryset=models.Section.objects.all(),
                                              widget=forms.CheckboxSelectMultiple)
    
class Breadcrumb():
    """
    Holds a breadcrumb for the header navigation bar
    """
    def __init__(self, description, link):
        self.description = description
        self.link = link
        
    def get_html_tag(self):
        if self.link:
            return u'<a href="{link}">{description}</a>'.format(description=self.description, link=self.link)
        else:
            return u'<span>{0}</span>'.format(self.description)

class PageNavigation():
    """
    Holds the current pagination state
    """
    
    def __init__(self, request, total_items):
        self.request = request
        self.total_items = total_items
        self.page_limit = int(request.GET.get('limit', settings.APTREPO_PAGINATION_LIMITS[0]))
        self.offset = int(request.GET.get('offset', 0))

    def current_page_number(self):
        return self.offset / self.page_limit + 1
    
    def has_previous(self):
        return self.current_page_number() > 1
    
    def has_next(self):
        return self.current_page_number() < self.total_pages()
    
    def previous_page_link(self):
        return self._get_page_url(self.current_page_number() - 1)
    
    def next_page_link(self):
        return self._get_page_url(self.current_page_number() + 1)
        
    def last_item_number(self):
        return min(self.offset + self.page_limit, self.total_items)
    
    def total_pages(self):
        return self.total_items / self.page_limit + 1 
    
    def position_summary(self):
        return '({0}-{1}/{2})'.format( self.offset + 1, self.last_item_number(), self.total_items )
    
    def specific_page_links(self):
        current_page = self.current_page_number()
        total_pages = self.total_pages()
        
        near_pages = range(max(1, current_page - 2), min(current_page + 2, total_pages) + 1)
        
        page_links = []
        for i in near_pages:
            page_links.append( {'page': i, 'link': self._get_page_url(i) if i!=current_page else '' } )
        if len(near_pages) > 1:
            if near_pages[0] != 1:
                page_links.insert(0, {'page': 1, 'link': self._get_page_url(1)})
            if near_pages[0] > 2:
                page_links.insert(1, {'page': '...', 'link': ''} )
                
            if near_pages[-1] < total_pages - 1:
                page_links.append( {'page': '...', 'link': ''} )
            if near_pages[-1] != total_pages:
                page_links.append({'page': total_pages, 'link': self._get_page_url(total_pages)})
                
        return page_links

    def _get_page_url(self, page_number):
        return _url_replace_get_param(self.request, 'offset', self.page_limit * (page_number - 1))


@handle_exception
@require_http_methods(["GET"])
def repository_home(request):
    """
    Outputs the home page
    """
    menu_items_list = [ 
        (_('Browse Repository'), _('Browse the packages in the repository'), 
            reverse('aptrepo:browse_distributions'), 'browse'),
        (_('Upload package'), _('Upload a package to the repository'), 
            reverse('aptrepo:package_upload'), 'upload'),
        (_('Recent Activity'), _('Review the change history in the repository'), 'history/', 'scroll'),
        (_('Download Public Key'), _('Download the GPG public key used for signing metadata'), 
            reverse('aptrepo.views.repo.files.gpg_public_key'), 'key'),
        (_('Administration'), _('Manage your repository (requires administrative privileges)'), 
            reverse('admin:index'), 'admin'),
        (_('Help'), _('Documentation for using the repository'), 'help/', 'help')
    ]
    
    return render_to_response('aptrepo/home.html', 
                              {'menu_items': menu_items_list, 'breadcrumbs': [] }, 
                              context_instance=RequestContext(request))
    

@handle_exception
@require_http_methods(["GET"])
def browse_distributions(request):
    """
    Outputs page to browse the repository distributions and sections
    """
    breadcrumbs = [ Breadcrumb(_('Distributions'), None) ]
    distributions_tree = {}
    all_sections = models.Section.objects.all().values(
        'id', 'name', 'distribution__name', 'distribution__id').order_by('name')
    for section in all_sections:
        distribution_name = section['distribution__name']
        if not distribution_name in distributions_tree:
            distributions_tree[distribution_name] = {
                'id': section['distribution__id'],
                'name': distribution_name,
                'sections': []
            }
        distributions_tree[distribution_name]['sections'].append( 
            dict((k, section[k]) for k in ('id','name') if k in section )
        ) 
         
    return render_to_response('aptrepo/browse_distributions.html', 
                              { 
                                'breadcrumbs': breadcrumbs, 
                                'distributions_tree': sorted(distributions_tree.iteritems()) 
                              }, 
                              context_instance=RequestContext(request))

@handle_exception
@require_http_methods(["GET"])
def get_distribution_info(request, distribution_name):
    """
    Returns JSON data on the distribution including other metadata metrics
    for the browse distribution page
    """
    distribution = models.Distribution.objects.get(name=distribution_name)
    f_entry = lambda header,value: (header, value)
    distribution_data = []
    distribution_data.append( f_entry( _('Name'), distribution.name ) )
    distribution_data.append( f_entry( _('Description'), distribution.description ) )
    distribution_data.append( f_entry( _('Label'), distribution.label ) )
    distribution_data.append( f_entry( _('Suite'), distribution.suite ) )
    distribution_data.append( f_entry( _('Origin'), distribution.origin ) )
    distribution_data.append( f_entry( _('Created'), 
        distribution.creation_date.strftime( _('%a %b %d %Y, %H:%M:%S') ) ) )
    distribution_data.append( f_entry( _('Supported Architectures'), ', '.join(distribution.get_architecture_list()) ) )
    distribution_data.append( f_entry( _('Number of Packages'), models.PackageInstance.objects.filter(
        section__distribution_id=distribution.id).count() ) )
    distribution_data.append( f_entry( _('Sections'), ', '.join(
        models.Section.objects.filter(
            distribution_id=distribution.id).order_by('name').values_list('name', flat=True)) ) )

    return HttpResponse(json.dumps(distribution_data))


def login(request):
    """
    Performs user login
    """
    breadcrumbs = [ Breadcrumb(_('Login'), None) ]
    return django.contrib.auth.views.login(request=request, template_name='aptrepo/login.html', 
                                           extra_context={ 'breadcrumbs': breadcrumbs, 'hide_login_link': True })

def logout(request):
    """
    Logs the user out
    """
    breadcrumbs = [ Breadcrumb(_('Logout'), None) ]    
    return django.contrib.auth.views.logout(request=request,
                                            extra_context={ 'breadcrumbs': breadcrumbs})

@handle_exception
@require_http_methods(["GET", "POST"])
def packages(request):
    """ 
    Handles package requests (no UI) 
    """
    if request.method == 'POST':
        return _packages_post(request)
    
    elif request.method == 'GET':
        # Get method at root will list all packages
        package_list = models.Package.objects.all().order_by('package_name')
        return render_to_response('aptrepo/packages_index.html', {'packages': package_list})
    
@handle_exception
@require_http_methods(["GET"])
def section_contents_list(request, distribution, section):
    section_obj = models.Section.objects.get(distribution__name=distribution, name=section)
    instances = models.PackageInstance.objects.filter(section=section_obj)
    return render_to_response('aptrepo/section_contents.html', 
                              { 'section' : section_obj, 
                                'package_instances': instances} )

def upload_success(request):
    """
    Successful upload view
    """
    return HttpResponse(_('Package successfully uploaded.'))


def remove_success(request):
    """
    Successful removal view
    """
    return HttpResponse(_('Package successfully removed.'))


@handle_exception
@require_http_methods(["GET", "POST"])
@login_required
@csrf_protect
def upload(request, distribution_name=None, section_name=None):
    """ 
    Provides a form to upload packages
    """
    
    # load the section if it was part of the URL
    target_section = None
    if distribution_name and section_name:
        target_section = _find_section( distribution_name, section_name )

    sections = []    
    if request.method == 'POST':
        initial_data = {}
        if target_section:
            initial_data['sections'] = [target_section]
        form = UploadPackageForm(data=request.POST, 
                                 files=request.FILES, 
                                 initial=initial_data)
        
        # TODO why is this explicit full_clean() call required?
        form.full_clean()   
        
        if form.is_valid():
            try:
                file_to_add = form.cleaned_data['file']
                
                # determine if this an URL (requiring a temporary download) or the file
                # content was included with the POST request
                if isinstance(file_to_add, unicode):
                    file_to_add = TemporaryDownloadedFile(file_to_add)
                    file_to_add.download()
                else:
                    file_to_add = request.FILES['file'] 
                    
                sections = form.cleaned_data['sections']
                comment = form.cleaned_data['comment']
                return _handle_add_file_to_repository(request, sections, 
                                                      file_to_add, comment)
            finally:
                if isinstance(file_to_add, TemporaryDownloadedFile):
                    file_to_add.close()

    elif request.method == 'GET':
        form = UploadPackageForm(initial={'sections': [target_section]})
        
    if target_section:
        breadcrumbs = [
                       Breadcrumb(_('Distributions'), reverse('aptrepo:browse_distributions')),
                       Breadcrumb(distribution_name, None),
                       Breadcrumb(
                            section_name, 
                            reverse(
                                    'aptrepo:section_contents', 
                                    kwargs={'distribution':distribution_name, 'section':section_name})),
                       Breadcrumb(_('Upload'), None)]
    else:
        breadcrumbs = [
                       Breadcrumb(_('Packages'), None),
                       Breadcrumb(_('Upload'), None) ]
        
    return render_to_response('aptrepo/upload_package.html', 
                              {'form':form, 'breadcrumbs': breadcrumbs,
                               'upload_target': target_section }, 
                              context_instance=RequestContext(request))
    
    
@handle_exception
@require_http_methods(["POST"])
@login_required
def delete_package_instance(request):
    """
    Basic HTTP POST call to remove a package instance
    """
    # extract the package instance identifier
    package_instance_id = 0
    if 'package_instance' in request.POST:
        package_instance_id = request.POST['package_instance']
    else:
        package_instance = models.PackageInstance.objects.get(
            section__distribution__name=request.POST['distribution'],
            section__name=request.POST['section'],
            package__package_name=request.POST['name'],
            package__architecture=request.POST['architecture'],
            package__version=request.POST['version'])
        package_instance_id = package_instance.id
        
    return _handle_remove_package(request, package_instance_id)

@handle_exception
@require_http_methods(["GET"])
def history(request, distribution=None, section=None):
    """
    Displays the history for distribution or section within the repository
    
    distribution - name of distribution to filter (defaults to entire repository)
    section - name of section to filter (defaults to all sections in a distribution)
    
    offset - offset within historical query (defaults to 0)
    limit - page limit (see util.constrain_queryset)
     
    """
    # set the default view type
    view_type = request.GET.get('view_type', 'simple')
    limit = request.GET.get('limit', settings.APTREPO_PAGINATION_LIMITS[0])
    
    # construct query and breadcrumb links based on query parameters
    root_distribution_url = reverse('aptrepo:browse_distributions')
    breadcrumbs = [Breadcrumb(_('Distributions'), root_distribution_url)]
    if distribution:
        breadcrumbs.append( 
            Breadcrumb(distribution, "{0}{1}".format(root_distribution_url, distribution)) 
        )
        if section:
            breadcrumbs.append(
                Breadcrumb(
                    section, 
                    "{0}{1}/sections/{2}".format(root_distribution_url, distribution, section))
            )
    breadcrumbs.append( Breadcrumb(_('Recent History'), None) )
    
    # retrieve historical actions
    repository = get_repository_controller(request=request)        
    actions = repository.get_historical_actions(distribution, section)

    # set the navigable URLs
    urls = {}
    urls['view_simple'] = _url_replace_get_param(request, 'view_type', 'simple')
    urls['view_table'] = _url_replace_get_param(request, 'view_type', 'table')
    urls['change_pagination_links'] = []
    for limit in settings.APTREPO_PAGINATION_LIMITS:
        urls['change_pagination_links'].append(
            { 'limit': limit, 'url': _url_replace_get_param(request, 'limit', limit) }
    )
    
    # render result along with data for pagination    
    page_navigate = PageNavigation(request, actions.count())
    return render_to_response('aptrepo/history.html', 
                              {'breadcrumbs': breadcrumbs, 
                               'current_area': breadcrumbs[-2],
                               'actions': constrain_queryset(request, actions),
                               'page_navigate': page_navigate,
                               'urls': urls,
                               'view_type': view_type },
                              context_instance=RequestContext(request))  


@handle_exception
@require_http_methods(["GET"])
def help(request):
    return HttpResponse('Not implemented yet')

@handle_exception
@require_http_methods(["POST"])
@login_required
def _packages_post(request):
    """ 
    POST requests will upload a package and create a new record 
    (separate internal method to enforce authentication only for POST, not GET)
    """
    uploaded_file = request.FILES['file']
    sections = [ _find_section( request.POST['distribution'], request.POST['section'] ) ]
    comment = request.POST['comment']

    # store result and redirect to success page
    return _handle_add_file_to_repository(request, sections, uploaded_file, comment)

def _handle_add_file_to_repository(request, sections, file_to_add, comment):
    """ 
    Handles a successfully uploaded files 
    """
    # add the package
    repository = get_repository_controller(request=request)
    args = {'sections':sections, 'comment':comment}
    if isinstance(file_to_add, TemporaryDownloadedFile):
        args['package_fh'] = file_to_add.get_fh()
        args['package_path'] = file_to_add.get_path()
        args['package_size'] = file_to_add.get_size()
    else:
        args['uploaded_package_file'] = file_to_add
        
    repository.add_package(**args)
    return HttpResponseRedirect(reverse('aptrepo:package_upload_success'))
    
def _handle_remove_package(request, package_instance_id):
    """
    Handles removing packages
    """
    repository = get_repository_controller(request=request)
    repository.remove_package(package_instance_id)
    return HttpResponseRedirect(reverse('aptrepo:package_delete_success'))

def _url_replace_get_param(request, param_name, param_value):
    """
    Constructs a new URL by replacing a selected parameter
    """
    modified_params = request.GET.copy()
    if param_value:
        modified_params[param_name] = param_value
    elif param_name in modified_params:
        del modified_params[param_name]
    return '{0}?{1}'.format(request.path, modified_params.urlencode())

def _find_section(distribution_name, section_name):
    """
    Macro method for finding a section
    """
    return models.Section.objects.get(distribution__name=distribution_name,
                                      name=section_name)
    