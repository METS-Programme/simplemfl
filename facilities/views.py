from django.shortcuts import render
from django.db.models import Q
from django.conf import settings

from rest_framework import serializers, viewsets
from rest_framework import permissions

from facilities.models import OrgUnit, Identifier

# Serializers define the API representation.
class IdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Identifier
        fields = ('agency', 'context', 'external_id')

class OrgUnitSerializer(serializers.HyperlinkedModelSerializer):
    identifiers = IdentifierSerializer(required=False, many=True)

    class Meta:
        model = OrgUnit
        fields = ('href', 'name', 'uuid', 'level', 'orgunit_type', 'ownership', 'authority', 'active', 'parent', 'createdAt', 'updatedAt', 'identifiers', 'geometry')

# ViewSets define the view behavior.
# class IdentifierViewSet(viewsets.ModelViewSet):
#     queryset = Identifier.objects.all()
#     serializer_class = IdentifierSerializer

class OrgUnitViewSet(viewsets.ModelViewSet):
    queryset = OrgUnit.objects.all()
    serializer_class = OrgUnitSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

# TODO: inherit from OrgUnitViewSet?
class AdminUnitViewSet(viewsets.ModelViewSet):
    queryset = OrgUnit.objects.filter(Q(orgunit_type='ADMIN'))
    serializer_class = OrgUnitSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class FacilityViewSet(viewsets.ModelViewSet):
    queryset = OrgUnit.objects.filter(~Q(orgunit_type='ADMIN'))
    serializer_class = OrgUnitSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

def index(request):
    from django.db import connection

    cursor = connection.cursor()

    cursor.execute("select level, count(level) from facilities_orgunit group by level order by level asc")
    rows = cursor.fetchall()
    level_summary = [(settings.ORG_UNIT_LEVELS[level], count) for level,count in rows]

    cursor.execute("select ownership, count(ownership) from facilities_orgunit group by ownership order by ownership asc")
    rows = cursor.fetchall()
    ownership_map = dict(OrgUnit.OWNERSHIP_CHOICES)
    ownership_summary = [(ownership_map[ownership], count, (count/level_summary[-1][1])*100) for ownership,count in rows]

    context = {
        'level_summary': level_summary,
        'total_facilities': level_summary[-1][1],
        'ownership_summary': ownership_summary,
    }

    return render(request, 'facilities/index.html', context)
