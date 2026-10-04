from __future__ import annotations

import socket


def _sanitize(value: str) -> str:
    return "".join(
        c if c.isalnum() or c == "_" else "_" for c in str(value)
    )


class StatsdMetrics:
    """
    Fire-and-forget StatsD (UDP) metrics for streaming pipelines.

    Metric names: <prefix>.<stream>.<metric>[.<change_type>]
    The stream name is sanitized so it is a single statsd path segment.
    Safe to pickle: the socket is created lazily and never serialized.
    Failures to send are swallowed so metrics never break a batch.
    """

    def __init__(
        self,
        stream: str,
        host: str = "statsd-exporter",
        port: int = 9125,
        prefix: str = "delta_streaming",
    ):
        self._stream = _sanitize(stream)
        self._address = (host, port)
        self._prefix = prefix
        self._sock: socket.socket | None = None

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        state["_sock"] = None
        return state

    def _send(self, line: str) -> None:
        try:
            if self._sock is None:
                self._sock = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM
                )
            self._sock.sendto(line.encode(), self._address)
        except OSError:
            pass

    def _name(self, metric: str, *suffix: str) -> str:
        parts = [self._prefix, self._stream, metric]
        parts.extend(_sanitize(s) for s in suffix)
        return ".".join(parts)

    def _counter(self, name: str, value: int) -> None:
        self._send(f"{name}:{int(value)}|c")

    def _gauge(self, name: str, value: float) -> None:
        self._send(f"{name}:{value}|g")

    def _timer_ms(self, name: str, seconds: float) -> None:
        self._send(f"{name}:{seconds * 1000.0}|ms")

    def observe_batch_rows(self, rows: int) -> None:
        self._gauge(self._name("batch_rows"), rows)

    def processed(self, change_type: str, count: int) -> None:
        self._counter(self._name("processed", change_type), count)

    def merge_result(
        self, inserted: int, updated: int, deleted: int
    ) -> None:
        self._counter(self._name("merge", "inserted"), inserted)
        self._counter(self._name("merge", "updated"), updated)
        self._counter(self._name("merge", "deleted"), deleted)

    def observe_batch_duration(self, seconds: float) -> None:
        self._timer_ms(self._name("batch_duration"), seconds)

    def batch_succeeded(self) -> None:
        self._counter(self._name("batches", "succeeded"), 1)

    def batch_failed(self, exc: BaseException | None = None) -> None:
        self._counter(self._name("batches", "failed"), 1)

    def pending(self, rows: int) -> None:
        self._gauge(self._name("pending"), rows)

    def decorated(self, succeeded: int, failed: int) -> None:
        self._counter(self._name("decorated", "succeeded"), succeeded)
        self._counter(self._name("decorated", "failed"), failed)
