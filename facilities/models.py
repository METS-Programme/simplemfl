from django.db import models
from django.db.models import F
from django.conf import settings

from functools import lru_cache, partial
import re
import uuid

from mptt.models import MPTTModel, TreeForeignKey

class Identifier(models.Model):
    agency = models.CharField(max_length=64)
    context = models.CharField(max_length=64)
    external_id = models.CharField(max_length=32)

    class Meta:
        unique_together = (
            ('agency', 'context', 'external_id'),
        )

    def __str__(self):
        return '::'.join([self.agency, self.context, self.external_id])


def orgunit_cleanup_name(name_str):
    """
    Convert name to DHIS2 standard form and fix any whitespace issues (leading,
    trailing or repeated)
    """
    if name_str:
        name_str = name_str.strip() # remove leading/trailing whitespace
        name_str = re.sub(r'\s+', ' ', name_str) # standardise and "compress" all whitespace
        name_str = name_str.replace(' H/C I', ' HC I') # matches ' HC II', ' HC III' and ' HC IV'
        name_str = name_str.replace(' Health Centre I', ' HC I')
        name_str = name_str.replace(' Health Center I', ' HC I')
        name_str = name_str.replace(' HCIV', ' HC IV')
        name_str = name_str.replace(' HCII', ' HC II') # matches HC II and HC III
    return name_str

class OrgUnit(MPTTModel):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, db_index=True)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True)
    name = models.CharField(max_length=96, db_index=True)
    active = models.BooleanField(default=True)
    createdAt = models.DateTimeField(auto_now_add=True, verbose_name='created at')
    updatedAt = models.DateTimeField(auto_now=True, verbose_name='updated at')

    # TODO: find_proximity() - given a set of coordinates, return a list orgunits that might match at all levels (nearest hf, subcounties, district ...)
    # Build crude bounding box for admin units based on facilities with coordinates within them?
    geometry_str = models.TextField(null=True, verbose_name='geometry (GeoJSON string)')

    ORGUNIT_TYPE_CHOICES = (
        ('ADMIN', 'Administrative Unit'),
        ('BCDP', 'Blood Collection and Distribution Point'),
        ('CLINIC', 'Clinic'),
        ('HC II', 'HC II'),
        ('HC III', 'HC III'),
        ('HC IV', 'HC IV'),
        ('HOSPITAL', 'General Hospital'),
        ('NBB', 'National Blood Bank'),
        ('NRH', 'National Referral Hospital'),
        ('RBB', 'Regional Blood Bank'),
        ('RRH', 'Regional Referral Hospital'),
        ('SC', 'Special Clinic'),
    )

    OWNERSHIP_CHOICES = (
        ('GOVT', 'Government'),
        ('PNFP', 'PNFP'),
        ('PFP', 'PFP'),
    )

    AUTHORITY_CHOICES = (
        ('AIC', 'AIC'),
        ('CAFU', 'CAFU'),
        ('CBO', 'CBO'),
        ('GOVT', 'Government'),
        ('MOES', 'MOES'),
        ('MOH', 'MOH'),
        ('NGO', 'NGO'),
        ('PRIVATE', 'Private'),
        ('SDA', 'SDA'),
        ('SOS', 'SOS'),
        ('TASO', 'TASO'),
        ('UBTS', 'UBTS'),
        ('UCBHCA', 'UCBHCA'),
        ('UCMB', 'UCMB'),
        ('UMMB', 'UMMB'),
        ('UNHCR', 'UNHCR'),
        ('UOMB', 'UOMB'),
        ('UPDF', 'UPDF'),
        ('UPF', 'UPF'),
        ('UPMB', 'UPMB'),
        ('UPS', 'UPS'),
        ('URHB', 'URHB'),
    )

    orgunit_type = models.CharField(max_length=16, choices=ORGUNIT_TYPE_CHOICES, default='ADMIN', db_index=True, verbose_name='type')
    ownership = models.CharField(max_length=16, choices=OWNERSHIP_CHOICES, default='GOVT', db_index=True)
    authority = models.CharField(max_length=16, choices=AUTHORITY_CHOICES, default='GOVT', db_index=True)

    identifiers = models.ManyToManyField(Identifier)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        unique_together = (('name', 'parent'),)
        verbose_name = 'organisation unit'

    @classmethod
    def from_path_str(cls, path, path_sep='/'):
        return cls.from_path(path.split(path_sep))

    @classmethod
    def from_path(cls, *path_parts):
        current_node = None
        for p in path_parts:
            p = orgunit_cleanup_name(p)
            if p:
                ou_p, _ = cls.objects.get_or_create(name__iexact=str(p), parent=current_node, defaults={'name':str(p)})
                current_node = ou_p
            else:
                break # stop processing when you find blank/empty path component/name

        return current_node

    @classmethod
    @lru_cache(maxsize=1024)
    def from_path_recurse(cls, *path_parts):
        if len(path_parts) == 0:
            return None
        *parent_path, node_name = path_parts
        node_name = orgunit_cleanup_name(node_name)
        ou_parent = cls.from_path_recurse(*parent_path)
        ou, _ = cls.objects.get_or_create(name__iexact=node_name, parent=ou_parent, defaults={'name':node_name})
        return ou

    @staticmethod
    def level_names(max_level=None):
        if max_level is None:
            level_count = len(settings.ORG_UNIT_LEVELS)
        else:
            level_count = max_level + 1
        return tuple((settings.ORG_UNIT_LEVELS.get(i) for i in range(level_count) if settings.ORG_UNIT_LEVELS.get(i) is not None))

    @staticmethod
    def level_fields(max_level=None):
        #TODO: escape/replace any characters that would be an invalid field name
        return tuple(map(lambda x: x.lower().replace(' ', '_'), OrgUnit.level_names(max_level)))

    @staticmethod
    def level_dbfields(max_level=None, *ignore, prefix=''):
        if max_level is None:
            level_count = len(settings.ORG_UNIT_LEVELS)
        else:
            level_count = max_level + 1
        return tuple(reversed([prefix+(''.join(('parent__',)*i)+'name') for i in range(level_count)]))

    @staticmethod
    def level_annotations(max_level=None, *ignore, prefix=''):
        return dict(zip(OrgUnit.level_fields(max_level), [F(f) for f in OrgUnit.level_dbfields(max_level, prefix=prefix)]))

    @staticmethod
    def get_level_field(level):
        #TODO: escape/replace any characters that would be an invalid field name
        return settings.ORG_UNIT_LEVELS[level].lower().replace(' ', '_')

    @property
    def geometry(self):
        import json
        if self.geometry_str:
            return json.loads(self.geometry_str)
        else:
            return None

    #TODO: create 'geometry' setter property that checks for valid (Geo)JSON

    @property
    def identifiers_flat(self):
        return [str(x) for x in self.identifiers.all()]

    def __str__(self):
        return '%s [parent_id: %s]' % (self.name, str(self.parent_id),)
