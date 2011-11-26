from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from server.aptrepo import models
from server.aptrepo.views import get_repository_controller

class DistributionFeed(Feed):
    """
    RSS feed for repository distributions and sections
    """
    
    _MAX_NEWEST_ACTIONS = 25
    
    def get_object(self, request, distribution):
        return get_object_or_404(models.Distribution, name=distribution)
    
    def title(self, obj):
        return str(obj)

    def description(self, obj):
        return "Activity for distribution " + str(obj)
    
    def link(self, obj):
        return "/dists/" + obj.name
    
    def items(self, obj):
        repository = get_repository_controller()
        return repository.get_actions(distribution_id=obj.id)[:self._MAX_NEWEST_ACTIONS]

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
