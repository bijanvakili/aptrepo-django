from django.forms import FileField,FileInput,TextInput
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from server.aptrepo.util import span_text
from server.aptrepo.util.download import validate_download_url
from server.aptrepo.templatetags.url_extras import static_media_url
from server.aptrepo import models

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

class PackageSummaryWidget(TextInput, WidgetMediaMixin):
    """
    Widget summarizing a package instance
    """
    _BOLD_CSS_STYLE = 'bold_text'
    
    def render(self, name, value, attrs=None ):
        instance = models.PackageInstance.objects.get(id=value)
        summary_text = _('{0} version {1}').format(span_text(self._BOLD_CSS_STYLE, instance.package.package_name), 
                                                   span_text(self._BOLD_CSS_STYLE, instance.package.version))
        return mark_safe(render_to_string(
                                          'aptrepo/widgets/package_summary_widget.html',
                                          {'name': name,
                                           'instance': instance,
                                           'summary_text' : mark_safe(summary_text)}));
