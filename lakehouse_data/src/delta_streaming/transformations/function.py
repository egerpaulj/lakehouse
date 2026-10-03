from collections.abc import Callable

from pyspark.sql import DataFrame

from delta_streaming.core.transformer import ChangeTransformer

class FunctionTransformer(ChangeTransformer):
    """Adapter that turns a DataFrame function into a transformer."""

    def __init__(
        self,
        function: Callable[[DataFrame], DataFrame],
    ):
        self._function = function

    def transform(self, df: DataFrame) -> DataFrame:
        return self._function(df)
