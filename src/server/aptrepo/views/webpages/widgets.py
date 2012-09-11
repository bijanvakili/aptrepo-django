from django.forms import ClearableFileInput
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from server.aptrepo.templatetags.url_extras import static_media_url

class WidgetMediaMixin:
    class Media:
        css = {
            'all': (static_media_url('css/widgets.css'), ) 
        }
        js = ( static_media_url('js/widgets.js'), )

class AdvancedFileInputWidget(ClearableFileInput, WidgetMediaMixin):
    """
    Custom file input control
    """
    
    def render(self, name, value, attrs=None ):
        return mark_safe(render_to_string(
                                          'aptrepo/widgets/advanced_file_input.html',
                                          {'name': name}));
