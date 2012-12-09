import json
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
import django.contrib.auth.views
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
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
    next_redirect = forms.CharField(widget=forms.HiddenInput(),
                                    required=True)
    
class DeletePackageInstanceForm(forms.Form):
    """
    Form class for deleting package instances
    """
    instance = forms.ModelChoiceField(label=_('Package to Delete'),
                                      queryset=models.PackageInstance.objects.all(),
                                      widget=widgets.PackageSummaryWidget)
    comment = forms.CharField(label=_('Optional comment'),
                              required=False, 
                              max_length=models.Action.MAX_COMMENT_LENGTH)
    architectures = forms.MultipleChoiceField(label=_('Architectures to Delete'),
                                              widget=forms.CheckboxSelectMultiple)
    sections = forms.ModelMultipleChoiceField(label=_('Sections'),
                                              queryset=models.Section.objects.all(),
                                              widget=forms.CheckboxSelectMultiple)
    next_redirect = forms.CharField(widget=forms.HiddenInput())
    
    
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
    
    def limit_links(self):
        links = []
        for limit in settings.APTREPO_PAGINATION_LIMITS:
            links.append( { 'limit': limit, 
                          'url': _url_replace_get_param(self.request, 
                                                        'limit', limit) } )
        return links


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
                                'distributions_tree': sorted(distributions_tree.iteritems()),
                                'autodiscover_feed_title': _('Recent history for repository'),
                                'history_url_prefix' : reverse('aptrepo:all_history')
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
@require_http_methods(["GET"])
def section_contents_list(request, distribution, section):
    """
    List the instances in a repository section

    distribution - name of distribution to filter (defaults to entire repository)
    section - name of section to filter (defaults to all sections in a distribution)

    offset - offset within historical query (defaults to 0)
    limit - page limit (see util.constrain_queryset)
    """
    section_obj = models.Section.objects.get(distribution__name=distribution, name=section)
    
    # paginate the instance listings by package name
    unique_package_names = models.PackageInstance.objects \
        .filter(section=section_obj) \
        .values('package__package_name') \
        .distinct() \
        .order_by('package__package_name')
    instances = models.PackageInstance.objects.filter(section=section_obj,
        package__package_name__in=constrain_queryset(request, unique_package_names)). \
        order_by('package__package_name')
    
    # setup breadcrumbs
    root_distribution_url = reverse('aptrepo:browse_distributions') 
    breadcrumbs = [
                   Breadcrumb(_('Distributions'), root_distribution_url),
                   Breadcrumb(distribution, "{0}{1}".format(root_distribution_url, distribution)),
                   Breadcrumb( section, None) ]
    
    # render the instance listing for this page in the section
    page_navigate = PageNavigation(request, unique_package_names.count())
    return render_to_response('aptrepo/section_contents.html', 
                              { 'section' : section_obj,
                                'breadcrumbs': breadcrumbs,
                                'autodiscover_feed_title' : _('Recent history for section {0}').format(section),
                                'package_instances': instances,
                                'page_navigate': page_navigate,
                                'history_url_prefix' : 'history/',
                                'url_upload' : 'upload/'},
                                context_instance=RequestContext(request) )

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
                return redirect(form.cleaned_data['next_redirect'])
            
            finally:
                if isinstance(file_to_add, TemporaryDownloadedFile):
                    file_to_add.close()

    elif request.method == 'GET':
        form = UploadPackageForm(initial={'sections': [target_section], 
                                          'next_redirect': request.GET.get('next', reverse('aptrepo:repository_home'))})
        
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
@require_http_methods(["GET", "POST"])
@login_required
@csrf_protect
def delete_package_instances(request):
    """
    Page to remove package instances
    """
    if request.method == 'POST':
        # construct architecture list
        all_available_architectures = [unicode(models.Architecture.ARCHITECTURE_ALL)]
        for arch in models.Architecture.objects.all().values_list('name', flat=True):
            all_available_architectures.append(arch)
        
        # initialize the form and re-clean after extending the allowed architectures
        form = DeletePackageInstanceForm(data=request.POST)
        form.fields['architectures'].choices = map(lambda x: (x,x), all_available_architectures)
        form.full_clean()

        # validate and parse the form to determine the package instances to remove 
        if form.is_valid():
            primary_instance = form.cleaned_data['instance']
            package_instances = models.PackageInstance.objects.filter(
                package__package_name=primary_instance.package.package_name,
                package__version=primary_instance.package.version,
                package__architecture__in=form.cleaned_data['architectures'],
                section__in=form.cleaned_data['sections'])
        
            # remove the package instances
            repository = get_repository_controller(request=request)
            repository.remove_package_instances(package_instance_ids=package_instances.values_list('id', flat=True),
                                                comment=form.cleaned_data['comment'])
            return redirect(form.cleaned_data['next_redirect'])

    elif request.method == 'GET':
        instance = models.PackageInstance.objects.get(id=request.GET['instance']) 
        associated_packages = models.Package.objects.filter( \
            package_name=instance.package.package_name, 
            version=instance.package.version)
        available_architectures = associated_packages.values_list('architecture', flat=True)

        form = DeletePackageInstanceForm(initial={'instance': instance.id,
                                                  'sections': [instance.section], 
                                                  'architectures': available_architectures,
                                                  'next_redirect': request.GET.get('next', reverse('aptrepo:repository_home'))})
        
        available_sections = models.PackageInstance.objects.filter(package__in=associated_packages).values_list('section',
                                                                                                                flat=True) 
        form.fields['sections'].queryset = models.Section.objects.filter(id__in=available_sections)
        form.fields['architectures'].choices = map(lambda x: (x,x), 
                                                   available_architectures) 
        
        
    breadcrumbs = [Breadcrumb(_('Packages'), None),
                   Breadcrumb(_('Delete'), None)]
    return render_to_response('aptrepo/delete_package.html', 
                              {'form':form, 
                               'breadcrumbs': breadcrumbs }, 
                              context_instance=RequestContext(request))


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
            autodiscover_feed_title = _('Recent history for section {0}').format(section)
        else:
            autodiscover_feed_title = _('Recent history for distribution {0}').format(distribution)
    else:
        autodiscover_feed_title = _('Recent history for repository')
    breadcrumbs.append( Breadcrumb(_('Recent History'), None) )
    
    # retrieve historical actions
    repository = get_repository_controller(request=request)        
    actions = repository.get_historical_actions(distribution, section)

    # set the navigable URLs
    urls = {}
    urls['view_simple'] = _url_replace_get_param(request, 'view_type', 'simple')
    urls['view_table'] = _url_replace_get_param(request, 'view_type', 'table')
    
    # render result along with data for pagination    
    page_navigate = PageNavigation(request, actions.count())
    return render_to_response('aptrepo/history.html', 
                              {'breadcrumbs': breadcrumbs, 
                               'current_area': breadcrumbs[-2],
                               'actions': constrain_queryset(request, actions),
                               'page_navigate': page_navigate,
                               'urls': urls,
                               'view_type': view_type,
                               'autodiscover_feed_title': autodiscover_feed_title },
                               context_instance=RequestContext(request))  


@handle_exception
@require_http_methods(["GET"])
def help(request):
    return HttpResponse('Not implemented yet')

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
    