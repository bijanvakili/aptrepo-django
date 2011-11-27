from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.utils.feedgenerator import Atom1Feed
from server.aptrepo import models
from server.aptrepo.views import get_repository_controller

class BaseRepositoryFeed(Feed):
    """
    Common base class for syndication feeds
    """
    _MAX_NEWEST_ACTIONS = 25

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


class DistributionRSSFeed(BaseRepositoryFeed):
    """
    RSS feed for distributions
    """

    def get_object(self, request, distribution):
        return get_object_or_404(models.Distribution, name=distribution)
    
    def description(self, obj):
        return "Activity for distribution " + str(obj)
    
    def link(self, obj):
        return "/dists/" + obj.name
    
    def items(self, obj):
        repository = get_repository_controller()
        return repository.get_actions(distribution_id=obj.id).reverse()[:self._MAX_NEWEST_ACTIONS]


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
        return get_object_or_404(models.Section, distribution__name=distribution, name=section)
    
    def description(self, obj):
        return "Activity for section " + str(obj)
     
    def link(self, obj):
        return "/dists/{0}/{1}/".format(obj.distribution.name, obj.name)
    
    def items(self, obj):
        repository = get_repository_controller()
        return repository.get_actions(section_id=obj.id).reverse()[:self._MAX_NEWEST_ACTIONS]


class SectionAtomFeed(SectionRSSFeed):
    """
    ATOM feed for distributions
    """
    feed_type = Atom1Feed
    subtitle = SectionRSSFeed.description
