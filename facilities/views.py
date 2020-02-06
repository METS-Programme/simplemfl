from django.shortcuts import render
from django.db.models import Q, Max, Count
from django.http import HttpResponse
from django.urls import reverse
from django.conf import settings

import datetime
import csv
import io
import json
import requests

import rest_framework as drf
from rest_framework import serializers, viewsets
from rest_framework import permissions

from facilities.models import OrgUnit, Identifier

ORGUNIT_TYPE_MAP = dict(OrgUnit.ORGUNIT_TYPE_CHOICES)
OWNERSHIP_MAP = dict(OrgUnit.OWNERSHIP_CHOICES)
AUTHORITY_MAP = dict(OrgUnit.AUTHORITY_CHOICES)

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

def ou_to_geojson_obj(ou):
    geo_dict = dict(list([('type', 'Feature'), ('geometry', ou.get('geometry'))]))
    geo_dict['properties'] = dict([(k,v) for k,v in ou.items() if k!='geometry'])
    for k,v in geo_dict['properties'].items():
        if k in ('orgunit_type', 'ownership', 'authority'):
            if v in ORGUNIT_TYPE_MAP:
                geo_dict['properties'][k] = ORGUNIT_TYPE_MAP[v]
            if v in OWNERSHIP_MAP:
                geo_dict['properties'][k] = OWNERSHIP_MAP[v]
            if v in AUTHORITY_MAP:
                geo_dict['properties'][k] = AUTHORITY_MAP[v]
    return geo_dict

class GeoJSONOrgUnitSerializer(OrgUnitSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        return ou_to_geojson_obj(ret)

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

class HospitalViewSet(viewsets.ModelViewSet):
    queryset = OrgUnit.objects.filter(Q(orgunit_type='HOSPITAL') | Q(orgunit_type='RRH') | Q(orgunit_type='NRH'))
    serializer_class = GeoJSONOrgUnitSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    paginator = None

def index(request):
    from django.db import connection
    cursor = connection.cursor()

    cursor.execute("select level, count(level) from facilities_orgunit group by level order by level asc")
    rows = cursor.fetchall()
    level_summary = [(settings.ORG_UNIT_LEVELS[level], count) for level,count in rows]
    total_facilities = 0 if len(level_summary) == 0 else level_summary[-1][1]

    cursor.execute("select ownership, count(ownership) from facilities_orgunit group by ownership order by ownership asc")
    rows = cursor.fetchall()
    ownership_summary = [(OWNERSHIP_MAP[ownership], count, (count/total_facilities)*100) for ownership,count in rows]

    context = {
        'level_summary': level_summary,
        'total_facilities': total_facilities,
        'ownership_summary': ownership_summary,
    }

    return render(request, 'facilities/index.html', context)

def orgunit_and_children(request, ou_uuid):
    # TODO: when orgunit uuid not supplied default to top-level orgunit
    # TODO: display error for non-existent or invalid UUID
    ou = OrgUnit.objects.get(uuid=ou_uuid)
    context = {
        'orgunit': ou,
    }

    return render(request, 'facilities/orgunit_detail.html', context)


def region_type_summary(request):
    from django.db import connection
    cursor = connection.cursor()

    sql_str = """
    WITH regions AS (
    SELECT name, lft, rght FROM facilities_orgunit
    WHERE level=1)
    SELECT regions.name, orgunit_type, count(orgunit_type)
    FROM facilities_orgunit ou, regions
    WHERE ou.lft >= regions.lft AND ou.rght <= regions.rght
    AND ou.orgunit_type<>'ADMIN'
    GROUP BY regions.name, orgunit_type
    ORDER BY regions.name, orgunit_type;
    """

    cursor.execute(sql_str)
    rows = cursor.fetchall()
    region_type_summary = [(name, ORGUNIT_TYPE_MAP[orgunit_type], count) for name, orgunit_type, count in rows]

    context = {
        'page_title': 'Regions broken down by Facility Type',
        'summary': region_type_summary,
    }

    return render(request, 'facilities/grouped_summary.html', context)

def get_facility_geojson(request, ou_id):
    '''Returns an orgunit as a GeoJSON feature. All attributes (except geometry) are moved to the 'properties' collection.'''

    url = drf.reverse.reverse('orgunit-detail', args=[ou_id], request=request)
    r = requests.get(url)
    data = r.json()
    geo_data = ou_to_geojson_obj(data)

    return HttpResponse(json.dumps(geo_data, indent=4))

def facility_to_list(facility_obj, field_list, default=None):
    out_list = [getattr(facility_obj, field) for field in field_list]
    out_list = list(map(lambda x: str(x) if x is not None else default, out_list)) # replace empty/null/None with supplied default
    return out_list

def download_csv(request):
    facilities = OrgUnit.objects.filter(~Q(orgunit_type='ADMIN')).prefetch_related('identifiers')

    summary = {k: str(v) for k,v in facilities.aggregate(facilities_count=Count('uuid')).items()}
    last_modified_timestamp = OrgUnit.objects.latest('updatedAt').updatedAt
    summary['last_update'] =  str(last_modified_timestamp)

    # Create the HttpResponse object with the appropriate HTTP headers
    response = HttpResponse(content_type='text/csv')
    response['Last-Modified'] = last_modified_timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # HEAD request checks when data last changed
    if request.method == 'HEAD':
        return response # reply with just the last modified header
    
    response['Content-Disposition'] = 'attachment; filename="facilities_{0}.csv"'.format(summary['last_update'][:19])
    
    from django.core.cache import cache

    #TODO: switch to using a key:value combination of 'download_csv':(<last_update>,<csv_str>) which makes it easier to clear the cache
    cache_key = 'download_csv {0}'.format(summary['last_update'])
    cache.delete(cache_key)
    csv_str = cache.get(cache_key)

    if csv_str is None:
        str_output = io.StringIO()

        field_list = (
            'uuid', 'name', 'active', 'createdAt', 'updatedAt', 'geometry_str', 'orgunit_type', 'ownership', 'authority', 'identifiers'
        )
        
        writer = csv.writer(str_output, quoting=csv.QUOTE_NONNUMERIC)
        header_list = [h.upper() for h in field_list]
        writer.writerow(header_list) # CSV header row
        facilities_gen = (facility_to_list(f, field_list[:-1], default='')+[str(f.identifiers_flat)] for f in facilities)
        writer.writerows(facilities_gen)

        csv_str = str_output.getvalue()
        cache.set(cache_key, csv_str, None)
    
    response.write(csv_str)

    return response
