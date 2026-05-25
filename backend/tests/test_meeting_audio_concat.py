"""WebM fragment concat tests for browser MediaRecorder chunks."""
import os
import tempfile

from tars.meeting.audio_preprocess import concat_webm_fragments


def test_concat_webm_fragments_merges_bytes():
    with tempfile.TemporaryDirectory() as tmp:
        chunk1 = os.path.join(tmp, "a.webm")
        chunk2 = os.path.join(tmp, "b.webm")
        with open(chunk1, "wb") as f:
            f.write(b"HEADER")
        with open(chunk2, "wb") as f:
            f.write(b"CLUSTER")
        merged, cleanup = concat_webm_fragments([chunk1, chunk2])
        try:
            with open(merged, "rb") as f:
                data = f.read()
            assert data == b"HEADERCLUSTER"
        finally:
            for path in cleanup:
                os.unlink(path)
