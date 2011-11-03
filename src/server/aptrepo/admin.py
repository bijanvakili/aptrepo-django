from django.contrib import admin
from models import Architecture, Distribution, Section

class ArchitectureAdmin(admin.ModelAdmin):
    pass 

class SectionInline(admin.StackedInline):
    model = Section

class DistributionAdmin(admin.ModelAdmin):
    date_hierarchy = 'creation_date'
    inlines = [SectionInline]
    
admin.site.register(Architecture, ArchitectureAdmin)
admin.site.register(Distribution, DistributionAdmin)
