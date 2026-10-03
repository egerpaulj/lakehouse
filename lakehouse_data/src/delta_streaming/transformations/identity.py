from pyspark.sql import DataFrame

from delta_streaming.core.transformer import ChangeTransformer

class IdentityTransformer(ChangeTransformer):
    """Does not modify the DataFrame."""

    def transform(self, df: DataFrame) -> DataFrame:
        return df
