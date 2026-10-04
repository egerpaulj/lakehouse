"""Decorate rows of the silver (s0) table with LLM / embedding derived columns.

Decorators (select with --decorator):

* summary     - summarize ``text`` with llm-summary        -> ``summary``
* ner_nel     - NER/NEL with llm-ner-nel, stored as JSON   -> ``ner_nel``
* embeddings  - vectors from the embedding API (BGE-M3)    -> ``text_embedding``,
                                                              ``summary_embedding``

Each run decorates up to ``--limit`` rows that are still missing the value, so
runs are idempotent and failed rows are retried on the next run. The LLM
decorators talk to an Ollama instance (model, strategy and host configurable).
Results are merged back into s0 by key through Spark Connect.
"""

import argparse
import logging
import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql.types import ArrayType, FloatType, StringType, StructField, StructType

logger = logging.getLogger("decorate_s0")

DECORATORS = ("summary", "ner_nel", "embeddings")


def parse_args(argv=None) -> argparse.Namespace:
    env = os.environ.get
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decorator", required=True, choices=DECORATORS)
    parser.add_argument("--table", required=True, help="Silver table, e.g. crawler.responses_s0")
    parser.add_argument("--key-column", default="_id")
    parser.add_argument("--text-column", default="text")
    parser.add_argument("--limit", type=int, default=500, help="Max rows decorated per run")
    parser.add_argument("--batch-size", type=int, default=16, help="Rows merged per Delta commit")
    parser.add_argument("--model", default=env("DECORATOR_MODEL"), help="LLM model (summary / ner_nel)")
    parser.add_argument("--strategy", default=env("DECORATOR_STRATEGY", "ollama"), help="LLM inference strategy")
    parser.add_argument("--ollama-host", default=env("OLLAMA_HOST", "http://ollama:11434"))
    parser.add_argument("--embedding-api-url", default=env("EMBEDDING_API_URL", "http://embedding-api:8000"))
    return parser.parse_args(argv)


def chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def build_summary(args):
    from llm_summary.inference_api.summary_inference import SummaryInferenceProvider

    kwargs = {"strategy": args.strategy, "ollama_host": args.ollama_host}
    if args.model:
        kwargs["model"] = args.model
    provider = SummaryInferenceProvider(**kwargs)

    def run(rows):
        return [{"summary": provider.summarize(text=r["text"]).summary} for r in rows]

    return run, StructType([StructField("summary", StringType())])


def build_ner_nel(args):
    from llm_ner_nel.inference_api.relationship_inference import RelationshipInferenceProvider

    kwargs = {"strategy": args.strategy, "ollama_host": args.ollama_host}
    if args.model:
        kwargs["model"] = args.model
    provider = RelationshipInferenceProvider(**kwargs)

    def run(rows):
        return [
            {"ner_nel": provider.get_relationships(r["text"]).model_dump_json()}
            for r in rows
        ]

    return run, StructType([StructField("ner_nel", StringType())])


def build_embeddings(args):
    import requests

    def encode(texts):
        response = requests.post(
            f"{args.embedding_api_url.rstrip('/')}/embed",
            json={"texts": texts},
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    def run(rows):
        # Only compute vectors that are missing; keep existing ones.
        todo = []
        for i, r in enumerate(rows):
            if r["text_embedding"] is None and r["text"]:
                todo.append((i, "text_embedding", r["text"]))
            if r["summary_embedding"] is None and r["summary"]:
                todo.append((i, "summary_embedding", r["summary"]))
        vectors = encode([t[2] for t in todo]) if todo else []
        out = [
            {"text_embedding": r["text_embedding"], "summary_embedding": r["summary_embedding"]}
            for r in rows
        ]
        for (i, column, _), vector in zip(todo, vectors):
            out[i][column] = vector
        return out

    vector = ArrayType(FloatType())
    return run, StructType(
        [StructField("text_embedding", vector), StructField("summary_embedding", vector)]
    )


BUILDERS = {"summary": build_summary, "ner_nel": build_ner_nel, "embeddings": build_embeddings}

# Rows that still need work, plus the columns the decorator reads.
PENDING = {
    "summary": ("summary IS NULL", ["text"]),
    "ner_nel": ("ner_nel IS NULL", ["text"]),
    # Embeddings are only computed for rows that already have a summary.
    "embeddings": (
        "summary IS NOT NULL AND summary <> '' AND `{text}` IS NOT NULL AND `{text}` <> '' "
        "AND (text_embedding IS NULL OR summary_embedding IS NULL)",
        ["text", "summary", "text_embedding", "summary_embedding"],
    ),
}


def decorate_batch(spark, args, run, schema, key_schema, rows):
    """Run the decorator on rows and MERGE the results into the table."""
    results = []
    for row in rows:
        try:
            result = run([row])[0]
        except Exception:
            logger.exception("Decorator %s failed for %s", args.decorator, row["key"])
            continue
        results.append((row["key"], *[result[f.name] for f in schema.fields]))
    if not results:
        return 0

    view = f"_s0_decorated_{args.decorator}"
    full_schema = StructType([key_schema] + schema.fields)
    spark.createDataFrame(results, full_schema).createOrReplaceTempView(view)
    sets = ", ".join(f"target.`{f.name}` = source.`{f.name}`" for f in schema.fields)
    spark.sql(
        f"MERGE INTO {args.table} AS target USING {view} AS source "
        f"ON target.`{args.key_column}` = source.`{args.key_column}` "
        f"WHEN MATCHED THEN UPDATE SET {sets}"
    )
    return len(results)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)
    run, schema = BUILDERS[args.decorator](args)
    condition, columns = PENDING[args.decorator]
    condition = condition.format(text=args.text_column)
    select_cols = ", ".join(
        [f"`{args.key_column}` AS key"]
        + [
            f"`{args.text_column}` AS text" if c == "text" else f"`{c}`"
            for c in columns
        ]
    )

    spark = (
        SparkSession.builder.appName(f"decorate-{args.decorator}-{args.table}")
        .remote(os.environ.get("SPARK_CONNECT_URL", "sc://spark-connect:15002"))
        .getOrCreate()
    )
    try:
        text_filter = f"`{args.text_column}` IS NOT NULL AND `{args.text_column}` <> ''"
        where = condition if args.decorator == "embeddings" else f"({condition}) AND {text_filter}"
        pending = [
            r.asDict()
            for r in spark.sql(
                f"SELECT {select_cols} FROM {args.table} WHERE {where} LIMIT {args.limit}"
            ).collect()
        ]
        logger.info("%s: %d row(s) to decorate", args.decorator, len(pending))

        key_type = spark.table(args.table).schema[args.key_column]
        key_schema = StructField(args.key_column, key_type.dataType)
        done = 0
        for batch in chunks(pending, args.batch_size):
            done += decorate_batch(spark, args, run, schema, key_schema, batch)
        print(f"Decorated {done}/{len(pending)} row(s) with {args.decorator} in {args.table}")
        if pending and done == 0:
            sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
