"""
Pythonic wrapper around `PyLucene <http://lucene.apache.org/pylucene/>`_ search engine.

Provides high-level interfaces to indexes and documents,
abstracting away java lucene primitives.
"""

import warnings
import lucene
warnings.simplefilter('default', DeprecationWarning)

from .queries import Query, SortField, TermsFilter
from .documents import Document, Field, MapField, NestedField, NumericField, DateTimeField
from .indexers import TokenFilter, Analyzer, IndexSearcher, MultiSearcher, IndexWriter, Indexer, ParallelIndexer
from .spatial import PointField, PolygonField

assert lucene.VERSION >= '4.3'
if lucene.VERSION < '4.4':
    warnings.warn('Support for lucene 4.3 will be removed in the next release.', DeprecationWarning)
