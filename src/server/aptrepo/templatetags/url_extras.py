from django.conf import settings
from django import template 

register = template.Library()

@register.simple_tag
def static_media_url(path, disable_media_token=False):
    """
    Used to specify URLs to static media files.
    
    For debugging, this also appends parameter suffixes for debugging purposes to get around 
    client web browsers that cache stale files
    """
    return settings.STATIC_URL + path + \
        ('?{0}'.format(settings.STATIC_MEDIA_TOKEN) if settings.DEBUG and not disable_media_token else '')

@register.simple_tag
def raster_image_url(path):
    """
    Used to specify URLs to a static raster image
    
    As above, this can append a suffix for debugging purposes
    """
    return static_media_url('images/raster/' + path)
