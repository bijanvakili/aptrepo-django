from django.contrib import admin
from models import Architecture, Distribution, Section
from views import get_repository_controller

class ArchitectureAdmin(admin.ModelAdmin):
    """
    Administrative form for architectures
    """
    pass 


class SectionAdmin(admin.ModelAdmin):
    """
    Administrative form for sections
    """
    actions = ['prune']
    
    def prune(self, request, queryset):
        repository = get_repository_controller()
        repository.prune_sections(queryset.values_list('id', flat=True))
    prune.short_description = 'Prune'
    
    def get_readonly_fields(self, request, obj=None):
        """
        Override to make authorization fields read-only if authorization 
        is not enforced
        """
        if not obj or not obj.enforce_authorization:
            return self.readonly_fields + ('authorized_users', 'authorized_groups', )
        return self.readonly_fields


class DistributionAdmin(admin.ModelAdmin):
    """
    Administrative form for distributions
    """
    date_hierarchy = 'creation_date'
    
admin.site.register(Architecture, ArchitectureAdmin)
admin.site.register(Distribution, DistributionAdmin)
admin.site.register(Section, SectionAdmin)
