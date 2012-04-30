from django.conf import settings
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.utils.feedgenerator import Atom1Feed
from django.utils.translation import ugettext as _
from server.aptrepo import models
from server.aptrepo.views import get_repository_controller

class BaseRepositoryFeed(Feed):
    """
    Common base class for syndication feeds
    """
    def title(self, obj):
        return str(obj)

    def item_title(self, item):
        return item.summary
    
    def item_link(self, item):
        if item.package:
            return item.package.path.url
        else:
            return '/dists/{0}/{1}'.format(item.section.distribution.name, item.section.name)

    def item_author_name(self, item):
        return item.user

    def item_description(self, item):
        description = item.summary
        if item.comment:
            description += '\n' + item.comment
        if item.package:
            description += '\n\n' + item.package.control
            
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
            

# TODO Try and collapse the Repository, Distribution and Feed classes into one class which behaves based
#        on the queried object type

class RepositoryRSSFeed(BaseRepositoryFeed):
    """
    RSS feed for the entire repository
    """
    def get_object(self, request):
        self._init_query_limits(request)
        return None
    
    def description(self):
        return _("Activity for repository")
    
    def link(self):
        return "/"
    
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
        return "/dists/" + obj.name
    
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
        return "/dists/{0}/{1}/".format(obj.distribution.name, obj.name)
    
    def items(self, obj):
        repository = get_repository_controller()
        return self._constrain_result(repository.get_actions(section_id=obj.id))


class SectionAtomFeed(SectionRSSFeed):
    """
    ATOM feed for distributions
    """
    feed_type = Atom1Feed
    subtitle = SectionRSSFeed.description
