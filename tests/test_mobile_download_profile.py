import os
import tempfile
import unittest

from backend.zsxq_file_downloader import ZSXQFileDownloader
from backend.zsxq_request_profiles import (
    build_zsxq_file_stream_headers,
    build_zsxq_mobile_headers,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""
        self.headers = {}

    def json(self):
        return self._payload

    def close(self):
        pass


class RecordingSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


class MobileDownloadProfileTest(unittest.TestCase):
    def test_mobile_headers_identify_as_phone(self):
        headers = build_zsxq_mobile_headers("a=b", "123")

        self.assertEqual("?1", headers["Sec-Ch-Ua-Mobile"])
        self.assertNotEqual('"Windows"', headers["Sec-Ch-Ua-Platform"])
        self.assertIn("Mobile", headers["User-Agent"])
        self.assertEqual("api.zsxq.com", headers["Host"])

    def test_file_stream_headers_do_not_force_api_host_or_cookie(self):
        headers = build_zsxq_file_stream_headers("a=b", "123")

        self.assertNotIn("Host", headers)
        self.assertNotIn("Cookie", headers)
        self.assertEqual("*/*", headers["Accept"])
        self.assertIn("Mobile", headers["User-Agent"])

    def test_download_url_uses_mobile_profile_first(self):
        payload = {
            "succeeded": True,
            "resp_data": {"download_url": "https://download.example.test/file.bin"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "files.db")
            downloader = ZSXQFileDownloader("a=b", "123", db_path=db_path, download_dir=tmpdir)
            try:
                downloader.smart_delay = lambda: None
                downloader.session = RecordingSession(FakeResponse(payload=payload))

                download_url = downloader.get_download_url(456)
                first_call_headers = downloader.session.calls[0]["headers"]
            finally:
                downloader.close()

        self.assertEqual("https://download.example.test/file.bin", download_url)
        self.assertEqual("?1", first_call_headers["Sec-Ch-Ua-Mobile"])

    def test_mobile_only_error_does_not_stop_whole_task(self):
        payload = {
            "succeeded": False,
            "code": 1030,
            "error_message": "Only mobile clients can download this file",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "files.db")
            downloader = ZSXQFileDownloader("a=b", "123", db_path=db_path, download_dir=tmpdir)
            try:
                downloader.smart_delay = lambda: None
                downloader.session = RecordingSession(FakeResponse(payload=payload))

                download_url = downloader.get_download_url(456)
                stop_flag = downloader.stop_flag
            finally:
                downloader.close()

        self.assertIsNone(download_url)
        self.assertFalse(stop_flag)


if __name__ == "__main__":
    unittest.main()
