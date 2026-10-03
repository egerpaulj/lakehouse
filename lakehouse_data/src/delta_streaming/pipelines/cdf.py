from typing import Optional

from pyspark.sql import SparkSession

from delta_streaming.core.config import StreamConfig
from delta_streaming.core.filter import ChangeFilter
from delta_streaming.core.sink import ChangeSink
from delta_streaming.core.source import ChangeSource
from delta_streaming.core.transformer import ChangeTransformer

class CDFStreamingPipeline:
    """
    Orchestrates:

        Source
          |
        Transformer
          |
        Filter
          |
        Sink
    """

    def __init__(
        self,
        source: ChangeSource,
        sink: ChangeSink,
        transformer: ChangeTransformer,
        change_filter: Optional[ChangeFilter] = None,
    ):
        self._source = source
        self._sink = sink
        self._transformer = transformer
        self._filter = change_filter

    def start(
        self,
        spark: SparkSession,
        config: StreamConfig,
    ):
        changes = self._source.read(spark)
        changes = self._transformer.transform(changes)

        if self._filter is not None:
            changes = self._filter.apply(changes)

        return self._sink.write(
            changes,
            config,
        )
