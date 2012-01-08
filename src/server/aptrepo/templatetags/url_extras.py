from django.conf import settings
from django import template 

register = template.Library()

@register.simple_tag
def media_file(path):
    """
    Used to specify URLs to static media files.
    
    For debugging, this also appends parameter suffixes for debugging purposes to get around 
    client web browsers that cache stale files
    """
    return settings.MEDIA_URL + path + ('?{0}'.format(settings.MEDIA_TOKEN) if settings.DEBUG else '')
