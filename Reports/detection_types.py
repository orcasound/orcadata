from typing import Dict, List, Optional

from pydantic import BaseModel


class Location(BaseModel):
    name: str
    longitude: float
    latitude: float


class Annotation(BaseModel):
    id: int
    startTime: float
    endTime: float
    confidence: float


class OrcaHelloDetection(BaseModel):
    id: str
    audioUri: str
    spectrogramUri: str
    location: Location
    timestamp: str
    annotations: List[Annotation]
    confidence: float
    found: str
    reviewed: bool
    comments: Optional[str] = None
    moderator: Optional[str] = None
    moderated: str
    tags: Optional[str] = None


class OrcaHelloApiResponseV1(BaseModel):
    detections: List[OrcaHelloDetection]


class OrcasoundDetection(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    feedId: str
    id: str
    listenerCount: Optional[int] = None
    playerOffset: str
    playlistTimestamp: int
    source: str
    sourceIp: Optional[str] = None
    timestamp: str
    visible: bool


class OrcasoundFeed(BaseModel):
    id: str
    name: str
    nodeName: str
    slug: str


class OrcasoundListenerReport(BaseModel):
    category: Optional[str] = None
    detectionCount: int
    detections: List[OrcasoundDetection]
    feed: OrcasoundFeed
    id: str
    maxTime: str
    minTime: str
    visible: bool


# Cache models for month-bucket caching

class DateRange(BaseModel):
    """Date range for a month bucket in PST timezone"""
    min_pst: str
    max_pst: str


class MonthMetadata(BaseModel):
    """Metadata for a cached month bucket"""
    first_fetch: str
    last_updated: str
    detection_count: int
    date_range: DateRange
    complete: bool


class CacheIndex(BaseModel):
    """Cache index tracking all fetched months"""
    months: Dict[str, MonthMetadata]
    last_full_fetch: Optional[str] = None


# Models for Orcasound GraphQL API Detection resource


class OrcasoundFeedGQL(BaseModel):
    """Feed info from Orcasound GraphQL Detection query"""
    id: str
    name: str
    slug: str
    nodeName: str


class OrcasoundDetectionGQL(BaseModel):
    """Detection from Orcasound GraphQL API (Detection resource type)"""
    id: str
    timestamp: str  # ISO datetime e.g. "2026-01-03T03:41:04.000000Z"
    source: str  # "HUMAN" or "MACHINE"
    category: Optional[str] = None  # "WHALE", "VESSEL", "OTHER", or None
    feedId: str
    playlistTimestamp: int  # Unix epoch timestamp
    playerOffset: str  # Decimal as string
    description: Optional[str] = None
    listenerCount: Optional[int] = None
    visible: Optional[bool] = None
    feed: OrcasoundFeedGQL
