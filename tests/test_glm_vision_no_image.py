import unittest
from unittest import mock

import glm_vision


class TestGlmVisionNoImage(unittest.TestCase):
    def test_analyze_screenshot_requires_images(self):
        called = {"count": 0}

        def fake_create(*args, **kwargs):
            called["count"] += 1
            raise RuntimeError("should not call")

        with mock.patch.object(glm_vision.client.chat.completions, "create", side_effect=fake_create):
            result = glm_vision.analyze_screenshot([])

        self.assertIn("error", result)
        self.assertEqual(called["count"], 0)


if __name__ == "__main__":
    unittest.main()
