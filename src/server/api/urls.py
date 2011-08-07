from django.conf.urls.defaults import *
from piston.resource import Resource
import handlers

package_resource=Resource(handler=handlers.PackageHandler)
distribution_resource=Resource(handler=handlers.DistributionHandler)
section_resource=Resource(handler=handlers.SectionHandler)
package_instance_resource=Resource(handler=handlers.PackageInstanceHandler)
action_resource=Resource(handler=handlers.ActionHandler)

urlpatterns = patterns('',
    # Packages
    (r'^packages/deb822/(?P<package_name>[^/]+)/(?P<version>[^/]+)/(?P<architecture>[^/]+)/{0,1}$', 
     package_resource),    
    (r'^packages/(?P<id>\d+)/{0,1}$', package_resource),
    (r'^packages/{0,1}$', package_resource),
    
    # Distributions
    (r'^distributions/{0,1}$', distribution_resource),
    (r'^distributions/(?P<distribution_id>\d+)/{0,1}$', distribution_resource),
    
    # Sections
    (r'^distributions/(?P<distribution_id>\d+)/sections/{0,1}$', section_resource),
    (r'^sections/{0,1}$', section_resource),
    (r'^sections/(?P<section_id>\d+)/{0,1}$', section_resource),
    
    # Package instances
    (r'^package-instances/(?P<instance_id>\d+)/{0,1}$', 
     package_instance_resource),
    (r'^sections/(?P<section_id>\d+)/package-instances/{0,1}$', 
     package_instance_resource),
    (r'^sections/(?P<section_id>\d+)/package-instances/deb822/(?P<package_name>[^/]+)/(?P<version>[^/]+)/(?P<architecture>[^/]+)/{0,1}$', 
     package_instance_resource),
    
    # Actions
    (r'^actions/{0,1}$', action_resource),
    (r'^distributions/(?P<distribution_id>\d+)/actions/{0,1}$', action_resource),
    (r'^sections/(?P<section_id>\d+)/actions/{0,1}$', action_resource),
)
