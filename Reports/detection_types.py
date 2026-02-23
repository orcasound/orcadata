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


# Models for combined/preprocessed detection data


class HydrophoneLocation(BaseModel):
    """Unified hydrophone location metadata from all sources"""
    slug: str  # Canonical identifier (e.g., "sunset-bay")
    display_name: str  # Human-readable name
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    orcahello_name: Optional[str] = None  # Name as it appears in OrcaHello API
    orcasound_feed_name: Optional[str] = None  # Name from Orcasound feed
    orcasound_feed_slug: Optional[str] = None  # Slug from Orcasound feed
    orcasound_node_name: Optional[str] = None  # Node name (e.g., "rpi_sunset_bay")


class HydrophoneLocationsFile(BaseModel):
    """Complete hydrophone locations reference file"""
    locations: List[HydrophoneLocation]
    name_to_slug: Dict[str, str]  # Any name variant -> canonical slug


class CombinedDetection(BaseModel):
    """Unified detection record from OrcaHello or Orcasound, for CSV export"""
    source: str  # orcahello_moderated | orcahello_unmoderated | orcasound
    detection_id: str  # Original ID from source API
    timestamp_utc: str  # ISO 8601 UTC timestamp
    timestamp_unix: int  # Unix epoch seconds
    timestamp_pacific: str  # ISO 8601 in US/Pacific timezone
    year_month_pacific: str  # YYYY-MM in Pacific time
    year_pacific: int  # Year in Pacific time
    month_pacific: int  # Month (1-12) in Pacific time
    date_pacific: str  # YYYY-MM-DD in Pacific time
    location_slug: str  # Standardized location slug
    srkw_positive: bool  # True if whale detection confirmed
    comments: Optional[str] = None  # Human comments

    # OrcaHello-specific metadata
    meta_orcahello_moderator: Optional[str] = None
    meta_orcahello_tags: Optional[str] = None
    meta_orcahello_confidence: Optional[float] = None

    # Orcasound-specific metadata
    meta_orcasound_listener_count: Optional[int] = None
    meta_orcasound_category: Optional[str] = None
    meta_orcasound_hls_timestamp: Optional[int] = None
    meta_orcasound_hls_offset: Optional[str] = None


class HourlyLogbookEvent(BaseModel):
    """Hourly aggregated event from detections"""
    source: str  # orcahello_moderated | orcahello_unmoderated | orcasound
    location_slug: str  # Standardized location slug
    timestamp_pacific: str  # Rounded hour timestamp (YYYY-MM-DDTHH:00:00-08:00 or -07:00)
    timestamp_unix: int  # Unix epoch of the rounded hour
    year_month_pacific: str  # YYYY-MM in Pacific time
    year_pacific: int  # Year in Pacific time
    month_pacific: str  # Month (01-12) in Pacific time
    date_pacific: str  # YYYY-MM-DD in Pacific time
    hour_pacific: int  # Hour (0-23) in Pacific time
    detection_count: int  # Total detections in this hour
    detection_positive_count: int  # Count of srkw_positive=true detections
    srkw_positive: bool  # Whether hour is considered positive based on source-specific threshold
    detection_ids: str  # Semicolon-delimited list of detection IDs
    comments: str  # Semicolon-delimited concatenated comments


class DailyLogbookEvent(BaseModel):
    """Daily aggregated event from hourly events"""
    source: str  # orcahello_moderated | orcahello_unmoderated | orcasound
    location_slug: str  # Standardized location slug
    year_month_pacific: str  # YYYY-MM in Pacific time
    year_pacific: int  # Year in Pacific time
    month_pacific: str  # Month (01-12) in Pacific time
    date_pacific: str  # YYYY-MM-DD in Pacific time
    hourly_event_count: int  # Number of distinct hours with activity
    hourly_event_positive_count: int  # Count of hourly events where srkw_positive=True
    detection_count: int  # Total detections for the day
    detection_positive_count: int  # Count of srkw_positive=true detections
    detection_ids: str  # Semicolon-delimited list of all detection IDs
    comments: str  # Semicolon-delimited concatenated comments
