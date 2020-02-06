from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^regions_by_type/', views.region_type_summary, name='region-by-type'),
    url(r'^geojson/(?P<ou_id>[0-9]+).json', views.get_facility_geojson, name='facility-geojson'),
    url(r'^download/facilities.csv', views.download_csv, name='facilities-csv'),
    url(r'^listing/(?P<ou_uuid>[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})', views.orgunit_and_children, name='listing'),
]
