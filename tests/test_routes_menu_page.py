import os
import unittest

from dotenv import load_dotenv


class MenuPageRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        try:
            from run import app
        except ImportError as exc:
            raise unittest.SkipTest(f"Dependencies unavailable: {exc}") from exc

        app.testing = True
        cls.client = app.test_client()

    def test_menu_page_renders_static_html(self):
        response = self.client.get("/menu/test-business-id")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        body = response.get_data(as_text=True)
        self.assertIn("Download our mobile app", body)
        self.assertIn("https://github.com/Pingeru/qrmenu-mobile", body)


if __name__ == "__main__":
    unittest.main()

