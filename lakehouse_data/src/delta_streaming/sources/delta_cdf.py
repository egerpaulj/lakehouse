from pyspark.sql import DataFrame, SparkSession

from delta_streaming.core.config import StreamConfig
from delta_streaming.core.source import ChangeSource

class DeltaCDFSource(ChangeSource):
    """Reads a Delta table using Delta Change Data Feed."""

    def __init__(self, config: StreamConfig):
        self._config = config

    def read(self, spark: SparkSession) -> DataFrame:
        reader = (
            spark.readStream
            .format("delta")
            .option("readChangeFeed", "true")
        )

        if self._config.starting_version is not None:
            reader = reader.option(
                "startingVersion",
                self._config.starting_version,
            )
        elif self._config.starting_timestamp is not None:
            reader = reader.option(
                "startingTimestamp",
                self._config.starting_timestamp,
            )

        return reader.table(self._config.source_table)
