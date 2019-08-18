from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import csv
import json

from facilities.models import OrgUnit, Identifier

# TODO: How to reset the orgunit cache on 'OrgUnit.from_path_recurse'? Reset at end of load from Excel??
class Command(BaseCommand):
    help = 'Load from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('CSV_FILE', nargs='+', help='CSV file containing facilities')

    def handle(self, *args, **options):
        with open(options['CSV_FILE'][0]) as csvfile:
            reader = csv.DictReader(csvfile) # assumes presence of header row and gobbles it up
            for row in reader:
                if row['NAME'] and row['FACILITY_LEVEL']:
                    # TODO: CSV files are being generated with a BOM (Byte Order Mark) which appears in the first item of the header. Fix this.
                    ou = OrgUnit.from_path_recurse(settings.ORG_UNIT_ROOT_NAME, row['\ufeffREGION'], row['SUB_REGION'], row['DISTRICT'], row['SUBCOUNTY'], row['NAME'])
                    ou_dirty = False
                    if ou.active != (row['OPERATIONAL STATUS'].strip() == 'Functional'):
                        ou.active = row['OPERATIONAL STATUS'].strip() == 'Functional'
                        ou_dirty = True
                    if row['UID']:
                        ou_identity, identity_created = Identifier.objects.get_or_create(agency='MOH', context='DHIS2', external_id=row['UID'])
                        if identity_created:
                            ou_identity.save()
                        ou.identifiers.add(ou_identity)
                        ou_dirty = True
                    if row['FACILITY_LEVEL']:
                        ou.orgunit_type = row['FACILITY_LEVEL'].upper()
                        ou_dirty = True
                    if row['OWNERSHIP_NAME']:
                        ou.ownership = row['OWNERSHIP_NAME'].upper()
                        ou_dirty = True
                    if row['AUTHORITY_NAME']:
                        ou.authority = row['AUTHORITY_NAME'].upper()
                        ou_dirty = True
                    if row['COORDINATES']:
                        ou_coords = json.loads(row['COORDINATES'])
                        ou_geom = dict([('type', 'Point'), ('coordinates', ou_coords)])
                        ou.geometry_str = json.dumps(ou_geom)
                        ou_dirty = True

                    if ou_dirty:
                        ou.save()
