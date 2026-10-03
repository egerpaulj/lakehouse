from abc import ABC, abstractmethod

from pyspark.sql import DataFrame, SparkSession

class ChangeSource(ABC):
    """Abstraction for a streaming change source."""

    @abstractmethod
    def read(self, spark: SparkSession) -> DataFrame:
        """Return a streaming DataFrame."""
        raise NotImplementedError
