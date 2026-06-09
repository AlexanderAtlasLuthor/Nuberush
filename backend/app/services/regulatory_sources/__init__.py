"""Regulatory source acquisition layer (F2.27.7.A).

The external-acquisition seam for regulatory ingestion: a source client /
parser abstraction plus the FDA/public-source parser. This package is pure —
it normalizes raw source items into `ParsedNotice` value objects and does NOT
persist anything, call the ingestion/matching/alert pipeline, mutate product
compliance, or touch the alert lifecycle. Wiring it into that pipeline is a
later subphase (F2.27.7.C).
"""

from app.services.regulatory_sources.base import RegulatorySourceClient
from app.services.regulatory_sources.base import RegulatorySourceFetchError
from app.services.regulatory_sources.base import RegulatorySourceParseError
from app.services.regulatory_sources.base import RegulatorySourceParser
from app.services.regulatory_sources.base import StaticRegulatorySourceClient
from app.services.regulatory_sources.fda import FDA_SOURCE_KIND
from app.services.regulatory_sources.fda import FdaRegulatorySourceClient
from app.services.regulatory_sources.fda import FdaRegulatorySourceParser
from app.services.regulatory_sources.fda import parse_fda_notice
from app.services.regulatory_sources.types import MATCHER_PRODUCT_KEYS
from app.services.regulatory_sources.types import ParsedNotice


__all__ = [
    "ParsedNotice",
    "MATCHER_PRODUCT_KEYS",
    "RegulatorySourceClient",
    "RegulatorySourceParser",
    "RegulatorySourceParseError",
    "RegulatorySourceFetchError",
    "StaticRegulatorySourceClient",
    "FdaRegulatorySourceParser",
    "FdaRegulatorySourceClient",
    "parse_fda_notice",
    "FDA_SOURCE_KIND",
]
