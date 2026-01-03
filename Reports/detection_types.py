from typing import List, Optional

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


class Detection(BaseModel):
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


class MetadataEntry(BaseModel):
    type: str  # "start", "server_info", "page_complete", "complete"
    base_url: Optional[str] = None
    timeframe: Optional[str] = None
    records_per_page: Optional[int] = None
    started_utc: Optional[str] = None
    start_page: Optional[int] = None
    max_pages: Optional[int] = None
    total_pages_header: Optional[int] = None
    total_records_header: Optional[int] = None
    page: Optional[int] = None
    count: Optional[int] = None
    timestamp: Optional[str] = None
    finished_utc: Optional[str] = None
    total_pages_fetched: Optional[int] = None
    total_records_fetched: Optional[int] = None


class ApiResponseV1(BaseModel):
    detections: List[Detection]


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
