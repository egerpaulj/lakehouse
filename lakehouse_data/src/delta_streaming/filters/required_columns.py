from collections.abc import Sequence

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from delta_streaming.core.filter import ChangeFilter

class RequiredColumnsFilter(ChangeFilter):
    """
    Keeps inserts/updates only when all required columns are
    non-null and, for string columns, non-empty.

    Delete events always pass through.
    """

    def __init__(self, columns: Sequence[str]):
        if not columns:
            raise ValueError(
                "At least one required column must be provided."
            )

        self._columns = tuple(columns)

    def apply(self, df: DataFrame) -> DataFrame:
        required = F.lit(True)

        schema = df.schema

        for column_name in self._columns:
            field = schema[column_name]

            condition = F.col(column_name).isNotNull()

            if isinstance(field.dataType, StringType):
                condition = condition & (
                    F.trim(F.col(column_name)) != ""
                )

            required = required & condition

        return df.filter(
            (F.col("_change_type") == "delete")
            | required
        )
