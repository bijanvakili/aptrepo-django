from django.conf.urls.defaults import *
from piston.resource import Resource
import handlers

package_resource=Resource(handler=handlers.PackageHandler)
distribution_resource=Resource(handler=handlers.DistributionHandler)
section_resource=Resource(handler=handlers.SectionHandler)
packageinstance_resource=Resource(handler=handlers.PackageInstanceHandler)
action_resource=Resource(handler=handlers.ActionHandler)

urlpatterns = patterns('',
    # Packages
    (r'^packages/(?P<id>\d+)/{,1}$', package_resource),
    (r'^packages/(?P<name>\w+)/(?P<version>\w+)/(?P<architecture>\w+)/{,1}$', package_resource),
    
    # Distributions
    (r'^distributions/{,1}$', distribution_resource),
    (r'^distributions/(?P<distribution_id>\w+)/{,1}$', distribution_resource),
    
    # Sections
    (r'^distributions/(?P<distribution_id>\w+)/sections/{,1}$', section_resource),
    (r'^distributions/(?P<distribution_id>\w+)/sections/(?P<section_id>\w+){,1}$', section_resource),
    (r'^sections/{,1}$', section_resource),
    (r'^sections/(?P<section_id>\w+)/{,1}$', section_resource),
    
    # Package instances
    (r'^distributions/(?P<distribution_id>\w+)/sections/(?P<section_id>\w+)/packages/{,1}$', section_resource),
    (r'^distributions/(?P<distribution_id>\w+)/sections/(?P<section_id>\w+)/packages/(?P<instance_id>\d+)/{,1}$', section_resource),
    (r'^distributions/(?P<distribution_id>\w+)/sections/(?P<section_id>\w+)/packages/(?P<package_name>\w+)/(?P<version>\w+)/(?P<architecture>\w+)/{,1}$', section_resource),
    
    # Actions
    (r'^actions/{,1}$', action_resource),
    (r'^distributions/(?P<distribution_id>\w+)/actions/{,1}$', action_resource),
    (r'^distributions/(?P<distribution_id>\w+)/sections/(?P<section_id>\w+)/actions/{,1}$', action_resource),
    (r'^sections/(?P<section_id>\w+)/actions/{,1}$', action_resource),
)
