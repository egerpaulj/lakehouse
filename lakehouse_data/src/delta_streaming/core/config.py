from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class StreamConfig:
    """Configuration for a Delta CDF streaming pipeline."""

    source_table: str
    target_table: str
    checkpoint_location: str

    query_name: Optional[str] = None

    starting_version: Optional[int] = None
    starting_timestamp: Optional[str] = None
