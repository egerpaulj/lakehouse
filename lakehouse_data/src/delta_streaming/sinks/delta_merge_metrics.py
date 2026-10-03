# from __future__ import annotations

# from collections.abc import Sequence

# from delta.tables import DeltaTable
# from pyspark.sql import DataFrame, SparkSession

# from delta_streaming.core.config import StreamConfig
# from delta_streaming.core.sink import ChangeSink
# from delta_streaming.metrics import StreamingMetrics


# class DeltaCDFMergeSink(ChangeSink):
#     """
#     Applies Delta CDF records to a target Delta table using
#     foreachBatch + MERGE.

#     Default behavior:

#         insert            -> INSERT
#         update_postimage  -> UPDATE / INSERT
#         delete            -> DELETE

#     update_preimage is ignored.
#     """

#     DEFAULT_UPSERT_TYPES = (
#         "insert",
#         "update_postimage",
#     )

#     def __init__(
#         self,
#         spark: SparkSession,
#         merge_condition: str,
#         metrics: StreamingMetrics | None = None,
#         upsert_change_types: Sequence[str] | None = None,
#     ):
#         self._spark = spark
#         self._merge_condition = merge_condition
#         self._metrics = metrics

#         self._upsert_change_types = tuple(
#             upsert_change_types
#             or self.DEFAULT_UPSERT_TYPES
#         )

#     def write(
#         self,
#         df: DataFrame,
#         config: StreamConfig,
#     ):
#         def merge_batch(
#             batch_df: DataFrame,
#             batch_id: int,
#         ) -> None:
#             del batch_id

#             if batch_df.isEmpty():
#                 return

#             metrics = self._metrics
#             started_at = None

#             if metrics is not None:
#                 import time

#                 started_at = time.monotonic()

#             try:
#                 # --------------------------------------------------
#                 # Count the CDF records that are about to reach
#                 # the sink.
#                 #
#                 # These are INPUT records, not actual target
#                 # INSERT/UPDATE/DELETE counts.
#                 # --------------------------------------------------
#                 change_counts = {
#                     row["_change_type"]: row["count"]
#                     for row in (
#                         batch_df
#                         .groupBy("_change_type")
#                         .count()
#                         .collect()
#                     )
#                 }

#                 batch_rows = sum(change_counts.values())

#                 if metrics is not None:
#                     metrics.observe_batch_rows(batch_rows)

#                 # --------------------------------------------------
#                 # Execute the actual Delta MERGE.
#                 # --------------------------------------------------
#                 target = DeltaTable.forName(
#                     self._spark,
#                     config.target_table,
#                 )

#                 upsert_types = ", ".join(
#                     f"'{value}'"
#                     for value in self._upsert_change_types
#                 )

#                 (
#                     target.alias("target")
#                     .merge(
#                         batch_df.alias("source"),
#                         self._merge_condition,
#                     )
#                     .whenMatchedDelete(
#                         condition=(
#                             "source._change_type = 'delete'"
#                         )
#                     )
#                     .whenMatchedUpdateAll(
#                         condition=(
#                             "source._change_type "
#                             f"IN ({upsert_types})"
#                         )
#                     )
#                     .whenNotMatchedInsertAll(
#                         condition=(
#                             "source._change_type "
#                             f"IN ({upsert_types})"
#                         )
#                     )
#                     .execute()
#                 )

#                 # --------------------------------------------------
#                 # The MERGE succeeded.
#                 #
#                 # Only now do we count the CDF records as
#                 # successfully processed.
#                 # --------------------------------------------------
#                 if metrics is not None:
#                     for change_type, count in change_counts.items():
#                         metrics.processed(
#                             change_type=change_type,
#                             count=count,
#                         )

#                 # --------------------------------------------------
#                 # Retrieve the actual Delta MERGE operation metrics.
#                 #
#                 # These are the authoritative INSERT/UPDATE/DELETE
#                 # counts for the target table.
#                 # --------------------------------------------------
#                 if metrics is not None:
#                     self._record_merge_metrics(
#                         target=target,
#                         metrics=metrics,
#                     )

#                     metrics.batch_succeeded()

#             except Exception as exc:
#                 if metrics is not None:
#                     metrics.batch_failed(exc)

#                 # Important:
#                 # re-raise so Spark knows that the micro-batch failed.
#                 raise

#             finally:
#                 if metrics is not None and started_at is not None:
#                     import time

#                     metrics.observe_batch_duration(
#                         time.monotonic() - started_at,
#                     )

#                     # Push after the batch has reached a terminal
#                     # state from this callback's perspective.
#                     metrics.push()

#         writer = (
#             df.writeStream
#             .foreachBatch(merge_batch)
#             .option(
#                 "checkpointLocation",
#                 config.checkpoint_location,
#             )
#             .trigger(availableNow=True)
#         )

#         if config.query_name:
#             writer = writer.queryName(config.query_name)

#         return writer.start()

#     @staticmethod
#     def _record_merge_metrics(
#         target: DeltaTable,
#         metrics: StreamingMetrics,
#     ) -> None:
#         """
#         Record actual Delta MERGE operation metrics.

#         Delta exposes metrics such as:

#             numTargetRowsInserted
#             numTargetRowsUpdated
#             numTargetRowsDeleted

#         through table history.

#         This assumes this pipeline is the only writer to the target
#         table. With concurrent writers, history(1) is not sufficient
#         to identify the MERGE transaction unambiguously.
#         """

#         history = (
#             target.history(1)
#             .select(
#                 "operation",
#                 "operationMetrics",
#             )
#             .collect()
#         )

#         if not history:
#             return

#         operation = history[0]

#         if operation["operation"] != "MERGE":
#             return

#         operation_metrics = (
#             operation["operationMetrics"] or {}
#         )

#         inserted = int(
#             operation_metrics.get(
#                 "numTargetRowsInserted",
#                 0,
#             )
#         )

#         updated = int(
#             operation_metrics.get(
#                 "numTargetRowsUpdated",
#                 0,
#             )
#         )

#         deleted = int(
#             operation_metrics.get(
#                 "numTargetRowsDeleted",
#                 0,
#             )
#         )

#         metrics.merge_result(
#             inserted=inserted,
#             updated=updated,
#             deleted=deleted,
#         )