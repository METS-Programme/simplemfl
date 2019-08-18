from django.contrib import admin
from django.conf import settings

from mptt.admin import MPTTModelAdmin

from .models import OrgUnit, Identifier

def level_name_from_id(obj):
    return settings.ORG_UNIT_LEVELS[obj.level]

level_name_from_id.short_description = 'Level Name'

class OrgUnitAdmin(MPTTModelAdmin):
    list_display = ['name', 'uuid', 'level', level_name_from_id, 'createdAt', 'updatedAt']
    list_filter = ['ownership', 'authority', 'orgunit_type']
    fields = ['parent', 'uuid', 'name', 'active', ('orgunit_type', 'ownership', 'authority'), 'identifiers', 'geometry_str']
    readonly_fields = ['uuid', 'identifiers']
    search_fields = ['name', 'identifiers__external_id']

class IdentifierAdmin(admin.ModelAdmin):
    list_display = ['agency', 'context', 'external_id']

admin.site.register(OrgUnit, OrgUnitAdmin)
admin.site.register(Identifier, IdentifierAdmin)
