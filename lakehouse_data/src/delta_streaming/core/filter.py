from abc import ABC, abstractmethod

from pyspark.sql import DataFrame

class ChangeFilter(ABC):
    """Abstraction for filtering change records."""

    @abstractmethod
    def apply(self, df: DataFrame) -> DataFrame:
        raise NotImplementedError
