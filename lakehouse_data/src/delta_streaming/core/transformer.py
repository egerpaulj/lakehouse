from abc import ABC, abstractmethod

from pyspark.sql import DataFrame

class ChangeTransformer(ABC):
    """Abstraction for transforming change records."""

    @abstractmethod
    def transform(self, df: DataFrame) -> DataFrame:
        raise NotImplementedError
