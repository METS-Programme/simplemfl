from django.shortcuts import render
from django.db.models import Q

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
