import apt_pkg
from django import template

register = template.Library()

@register.filter(name='deb822version_sort')
def deb822version_sort(list):
    return sorted(list, cmp=_compare_instances )

def _compare_instances(a, b):
    """
    Comparison function to first sort the versions in descending order with subset
    architectures in ascending order
    """
    version_compare_result = apt_pkg.version_compare(b.package.version, a.package.version)
    if version_compare_result == 0:
        return cmp(a.package.architecture, b.package.architecture)
    else:
        return version_compare_result
