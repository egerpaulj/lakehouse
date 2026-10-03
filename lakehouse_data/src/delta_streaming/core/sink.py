from abc import ABC, abstractmethod

from pyspark.sql import DataFrame
from pyspark.sql.streaming.query import StreamingQuery

from delta_streaming.core.config import StreamConfig

class ChangeSink(ABC):
    """Abstraction for writing change records."""

    @abstractmethod
    def write(
        self,
        df: DataFrame,
        config: StreamConfig,
    ) -> StreamingQuery:
        raise NotImplementedError
