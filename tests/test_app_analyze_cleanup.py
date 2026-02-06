import io
import os
import tempfile
import unittest
from unittest import mock

import app_llm as app


class TestAnalyzeCleanup(unittest.TestCase):
    def test_analyze_cleans_tempfiles_on_exception(self):
        created = []
        real_namedtemp = tempfile.NamedTemporaryFile

        def fake_namedtemp(*args, **kwargs):
            f = real_namedtemp(*args, **kwargs)
            created.append(f.name)
            return f

        def boom(_paths):
            raise RuntimeError("boom")

        with mock.patch.object(app.tempfile, "NamedTemporaryFile", side_effect=fake_namedtemp), \
             mock.patch.object(app, "analyze_screenshot", side_effect=boom):
            client = app.app.test_client()
            data = {
                "images": (io.BytesIO(b"fake"), "test.jpg"),
            }
            resp = client.post("/api/llm-generate-images", data=data, content_type="multipart/form-data")
            self.assertFalse(resp.json["success"])

        for path in created:
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
