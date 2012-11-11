from django.conf import settings
from django.contrib.syndication.views import Feed
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils.feedgenerator import Atom1Feed
from django.utils.translation import ugettext as _
from server.aptrepo import models
from server.aptrepo.templatetags.action_tags import summarize_action
from server.aptrepo.views import get_repository_controller

class BaseRepositoryFeed(Feed):
    """
    Common base class for syndication feeds
    """
    def title(self, obj):
        return str(obj)

    def item_title(self, item):
        if item.action_type == models.Action.UPLOAD:
            title_format = _('{package_name} uploaded to {section}')
        elif item.action_type == models.Action.DELETE:
            title_format = _('{package_name} removed from {section}')
        elif item.action_type == models.Action.COPY:
            title_format = _('{package_name} cloned to {section}')
        elif item.action_type == models.Action.PRUNE:
            title_format = _('{package_name} pruned from {section}')
            
        return title_format.format(package_name=item.package_name, 
                                   section=str(item.target_section))
    
    def item_link(self, item):
        # if the package exists, returns its URL
        # otherwise, return the URL of the section where this action took place
        package = self._get_package_for_item(item)
        if package:
            return package.path.url
        else:
            return self._get_section_url(item.target_section.distribution.name,
                                         item.target_section.name)

    def item_author_name(self, item):
        return item.user

    def item_description(self, item):
        description = summarize_action(item)
        if item.comment:
            description += '\n\n' + item.comment
        package = self._get_package_for_item(item)
        if package:
            description += '\n\n' + package.control
            
        return description.replace('\n', '<br/>')

    def item_pubdate(self, item):
        return item.timestamp
    
    def _init_query_limits(self, request):
        """
        Extract query limit parameters
        """
        self.offset = request.GET.get('offset', 0)
        self.limit = request.GET.get('limit', settings.APTREPO_PAGINATION_LIMITS[0])
        
    def _constrain_result(self, result):
        return result[self.offset:].reverse()[:self.limit]
    
    def _get_section_url(self, distribution_name, section_name):
            return reverse('aptrepo:section_contents', 
                           kwargs={ 'distribution':distribution_name,
                                    'section': section_name})
            
    def _get_package_for_item(self, item):
        query = models.Package.objects.filter(package_name=item.package_name, 
                                             version=item.version, 
                                             architecture=item.architecture)
        if query:
            return query[0]
        else:
            return None
            

# TODO Try and collapse the Repository, Distribution and Feed classes into one class which behaves based
#        on the queried object type

class RepositoryRSSFeed(BaseRepositoryFeed):
    """
    RSS feed for the entire repository
    """
    def get_object(self, request):
        self._init_query_limits(request)
        return _('Repository')
    
    def description(self, obj):
        return _("Activity for repository")
    
    def link(self, obj):
        return reverse('aptrepo:browse_distributions')
    
    def items(self):
        repository = get_repository_controller()
        return self._constrain_result(repository.get_actions())


class RepositoryAtomFeed(RepositoryRSSFeed):
    """
    ATOM feed for distributions
    """
    feed_type = Atom1Feed
    subtitle = RepositoryRSSFeed.description


class DistributionRSSFeed(BaseRepositoryFeed):
    """
    RSS feed for distributions
    """

    def get_object(self, request, distribution):
        self._init_query_limits(request)
        return get_object_or_404(models.Distribution, name=distribution)
    
    def description(self, obj):
        return _("Activity for distribution {0}".format(str(obj)))
    
    def link(self, obj):
        return reverse('aptrepo:distribution_info', kwargs={'distribution_name': obj.name})
    
    def items(self, obj):
        repository = get_repository_controller()
        return self._constrain_result(repository.get_actions(distribution_id=obj.id))


class DistributionAtomFeed(DistributionRSSFeed):
    """
    ATOM feed for distributions
    """
    feed_type = Atom1Feed
    subtitle = DistributionRSSFeed.description


class SectionRSSFeed(BaseRepositoryFeed):
    """
    RSS feed for sections
    """
    
    def get_object(self, request, distribution, section):
        self._init_query_limits(request)
        return get_object_or_404(models.Section, distribution__name=distribution, name=section)
    
    def description(self, obj):
        return _("Activity for section {0}".format(str(obj)))    
     
    def link(self, obj):
        return self._get_section_url(obj.distribution.name, obj.name)
    
    def items(self, obj):
        repository = get_repository_controller()
        return self._constrain_result(repository.get_actions(section_id=obj.id))


class SectionAtomFeed(SectionRSSFeed):
    """
    ATOM feed for distributions
    """
    feed_type = Atom1Feed
    subtitle = SectionRSSFeed.description
