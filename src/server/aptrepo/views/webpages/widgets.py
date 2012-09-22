from django.forms import FileField,FileInput
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from server.aptrepo.util.download import validate_download_url
from server.aptrepo.templatetags.url_extras import static_media_url

class WidgetMediaMixin:
    class Media:
        css = {
            'all': (static_media_url('css/widgets.css'), ) 
        }
        js = ( static_media_url('js/widgets.js'), )


class AdvancedFileField(FileField):
    """
    Subclassed file field to support specifying URLs instead of files
    """
    
    def __init__(self, *args, **kwargs):
        def validate_url(data):
            if isinstance(data, unicode):
                validate_download_url(data)
        
        kwargs['validators'] = kwargs.get('validators', []) + [validate_url]
        kwargs['widget'] = AdvancedFileInputWidget
        return super(AdvancedFileField, self).__init__(*args, **kwargs)
    
    def to_python(self, data):
        if isinstance(data, unicode):
            return data
        else:
            return super(AdvancedFileField, self).to_python(data)
        
    

class AdvancedFileInputWidget(FileInput, WidgetMediaMixin):
    """
    Custom file input control widget
    """
    
    def render(self, name, value, attrs=None ):
        return mark_safe(render_to_string(
                                          'aptrepo/widgets/advanced_file_input.html',
                                          {'name': name}));

    def value_from_datadict(self, data, files, name):
        """
        Override to return the visible text field if no file was attached
        """
        if name in files:
            return super(AdvancedFileInputWidget, self).value_from_datadict(data, files, name)
        else:
            return data[name + '_url']

    