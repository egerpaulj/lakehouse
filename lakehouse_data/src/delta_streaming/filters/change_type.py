from collections.abc import Sequence

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from delta_streaming.core.filter import ChangeFilter

class ChangeTypeFilter(ChangeFilter):
    """Filters records based on Delta CDF _change_type."""

    VALID_CHANGE_TYPES = frozenset(
        {
            "insert",
            "update_preimage",
            "update_postimage",
            "delete",
        }
    )

    def __init__(self, change_types: Sequence[str]):
        if not change_types:
            raise ValueError(
                "At least one change type must be provided."
            )

        invalid = set(change_types) - self.VALID_CHANGE_TYPES

        if invalid:
            raise ValueError(
                f"Invalid CDF change types: {sorted(invalid)}"
            )

        self._change_types = tuple(change_types)

    def apply(self, df: DataFrame) -> DataFrame:
        return df.filter(
            F.col("_change_type").isin(*self._change_types)
        )
