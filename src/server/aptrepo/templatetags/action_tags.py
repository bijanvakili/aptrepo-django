from django import template
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from server.aptrepo.models import Action
from server.aptrepo.util import AptRepoException, span_text

register = template.Library()

def _span_element(css_type_suffix, value):
    return span_text('history_item_' + css_type_suffix, value) 

def _section_link(section):
    return '<a href="{1}/">{0}</a>'.format(section.name, reverse('aptrepo:section_contents',kwargs={
        'distribution':section.distribution.name, 'section':section.name}))

@register.simple_tag
def summarize_action(action, include_html_formatting=True):
    """
    Provides an HTML formatted summary of an action
    """    
    params = {}
    for k in ['package_name', 'version', 'architecture']:
        params[k] = _span_element(k, getattr(action, k))
    if action.action_type != Action.PRUNE:
        params['user'] = _span_element('user', action.user)
    params['target_section'] = _section_link(action.target_section)
    
    if action.action_type == Action.UPLOAD:
        summary = _('{user} uploaded {package_name} version {version} \
            ({architecture}) to {target_section}')
    elif action.action_type == Action.DELETE:
        summary = _('{user} deleted {package_name} version {version} \
            ({architecture}) from {target_section}')
    elif action.action_type == Action.COPY:
        summary = _('{user} cloned {package_name} version {version} \
            ({architecture}) from {source_section} to {target_section}')
    elif action.action_type == Action.PRUNE:
        summary = _('{package_name} version {version} ({architecture}) pruned \
            from {target_section}')
        params['source_section'] = _section_link(action.source_section)
    else:
        raise AptRepoException('Unknown action')
    
    return summary.format(**params)

@register.simple_tag
def summarize_sections_for_action(action):
    """
    Provides an abbreviated summary of how an action was applied to a section
    """
    params = {'target_section': _section_link(action.target_section) }
    if action.action_type == Action.UPLOAD:
        summary = _('To {target_section}')
    elif action.action_type == Action.UPLOAD or action.action == Action.PRUNE:
        summary = _('From {target_section}')
    elif action.action_type == Action.COPY:
        summary = _('From {source_section} to {target_section}')
        params['source_section'] = _section_link(action.source_section) 
    else:
        raise AptRepoException('Unknown action')

    return summary.format(**params)
