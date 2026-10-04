import pickle
import socket

from delta_streaming.metrics import StatsdMetrics


def test_emits_statsd_lines_and_pickles():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2)
    metrics = StatsdMetrics("my-stream", "127.0.0.1", server.getsockname()[1])

    metrics.processed("update_postimage", 3)
    metrics.merge_result(inserted=1, updated=2, deleted=0)
    metrics = pickle.loads(pickle.dumps(metrics))
    metrics.batch_failed()

    lines = [server.recv(1024).decode() for _ in range(5)]
    assert lines == [
        "delta_streaming.my_stream.processed.update_postimage:3|c",
        "delta_streaming.my_stream.merge.inserted:1|c",
        "delta_streaming.my_stream.merge.updated:2|c",
        "delta_streaming.my_stream.merge.deleted:0|c",
        "delta_streaming.my_stream.batches.failed:1|c",
    ]
