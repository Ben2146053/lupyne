"""
Geospatial fields.

`Geohashing <http://en.wikipedia.org/wiki/Geohash>`_ is used to create an efficient index.

Dependencies:
 * Geohash: required for encoding.
 * pyproj: optional for transforming a projected coordinate system back into lat/longs.
 * shapely or django's geos: recommended for polygon support.
"""

import itertools
from functools import partial
import Geohash
import lucene
from documents import PrefixField

alphabet = Geohash.geohash.__base32
base32 = '0123456789abcdefghijklmnopqrstuv'
charmap = dict(zip(alphabet, itertools.count()))

def geoint(hash):
    "Convert geohash into integer."
    return int(''.join(base32[charmap[c]] for c in hash), len(base32))

def geonext(hash):
    "Return next lexicographic geohash."
    if hash[-1] < alphabet[-1]:
        return hash[:-1] + alphabet[charmap[hash[-1]] + 1]
    return geonext(hash[:-1]) + alphabet[0]

def geowalk(*hashes):
    "Generate all itermediate sequential geohashes."
    lower, upper = min(hashes), max(hashes)
    while lower <= upper:
        yield lower
        lower = geonext(lower)

class PointField(PrefixField):
    """Geospatial points, with optional projection.
    Geohashes create a tiered index of tiles.
    Points should still be stored if exact distances are required.
    
    :param precision: geohash encoding precision
    :param srid: projection coordinate system
    """
    def __init__(self, name, precision=12, srid=None, **kwargs):
        PrefixField.__init__(self, name, **kwargs)
        self.precision = precision
        # don't require pyproj if it's not used
        if srid is not None:
            from pyproj import Proj, transform
            self.transform = partial(transform, Proj(init='epsg:%i' % srid), Proj(init='epsg:4326'))
    def encode(self, x, y, precision=None):
        "Return geohash from point coordinates."
        if hasattr(self, 'transform'):
            x, y = self.transform(x, y)
        return Geohash.encode(y, x, precision or self.precision)
    def items(self, *points):
        "Generate geohashed tiles from points (lng, lat)."
        hashes = itertools.starmap(self.encode, set(points))
        return PrefixField.items(self, *sorted(set(hashes)))
    def query(self, x, y, precision=None):
        "Return lucene TermQuery for point at given precision."
        return PrefixField.query(self, self.encode(x, y, precision))
    def within(self, x, y, distance):
        "Return lucene Query for all tiles which could be within distance of given point."
        # tiles are roughly regular polygons, so radiating distance at 45 degrees should be sufficient
        radius = distance / (2**0.5)
        offsets = [(0, 0),
            (-distance, 0), (distance, 0), (0, -distance), (0, distance),
            (-radius, -radius), (-radius, radius), (radius, -radius), (radius, radius),
        ]
        hashes = set(self.encode(x+i, y+j) for i, j in offsets)
        # zoom out to a reasonable level of precision for given distance
        lower, upper = min(hashes), max(hashes)
        while geoint(upper) - geoint(lower) >= len(alphabet):
            lower, upper = lower[:-1], upper[:-1]
        q = lucene.BooleanQuery()
        for hash in geowalk(lower, upper):
            q.add(PrefixField.query(self, hash), lucene.BooleanClause.Occur.SHOULD)
        return q

class PolygonField(PointField):
    """GeoField which implicitly supports polygons (technically linear rings of points).
    Differs from points in that all necessary hash tiles are included to match the points' boundary.
    As with PointField, the tiered tiles are a search optimization, not a distance calculator.
    """
    def items(self, *polygons):
        "Generate all covered geohashed tiles from points."
        for points in polygons:
            hashes = itertools.starmap(self.encode, set(points))
            for field in PrefixField.items(self, *geowalk(*set(hashes))):
                yield field
