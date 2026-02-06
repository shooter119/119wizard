import unittest

import app_llm as app


class TestCaseTypeMapping(unittest.TestCase):
    def test_local_keyword_match_by_exact_name(self):
        case_types = app.load_case_types()
        self.assertGreater(len(case_types), 0)

        for case_item in case_types[:10]:
            name = case_item.get("name", "")
            with self.subTest(case_type=name):
                result = app.local_keyword_match(f"现场发生{name}", case_types)
                self.assertIsNotNone(result)
                self.assertEqual(result["case_type_name"], name)


if __name__ == "__main__":
    unittest.main()
