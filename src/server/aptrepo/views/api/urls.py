from django.conf.urls import patterns
from piston.resource import Resource
import auth
import handlers

resource_auth = {'authentication' : auth.DjangoSessionAuthentication() }

session_resource=Resource(handler=handlers.SessionHandler)
package_resource=Resource(handler=handlers.PackageHandler, **resource_auth)
distribution_resource=Resource(handler=handlers.DistributionHandler, **resource_auth)
section_resource=Resource(handler=handlers.SectionHandler, **resource_auth)
package_instance_resource=Resource(handler=handlers.PackageInstanceHandler, **resource_auth)
action_resource=Resource(handler=handlers.ActionHandler, **resource_auth)

urlpatterns = patterns('',
                       
    # Sessions
    (r'^sessions/{0,1}$', session_resource),
    (r'^sessions/(?P<session_key>[^/]+)/{0,1}$', session_resource),
                       
    # Packages
    (r'^packages/deb822/(?P<package_name>[^/]+)/(?P<version>[^/]+)/{0,1}$', 
     package_resource),
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
    (r'^sections/(?P<section_id>\d+)/package-instances/deb822/(?P<package_name>[^/]+)/(?P<version>[^/]+)/{0,1}$', 
     package_instance_resource),
    
    # Actions
    (r'^actions/{0,1}$', action_resource),
    (r'^distributions/(?P<distribution_id>\d+)/actions/{0,1}$', action_resource),
    (r'^sections/(?P<section_id>\d+)/actions/{0,1}$', action_resource),
)
