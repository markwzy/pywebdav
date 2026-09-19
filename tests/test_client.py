"""不访问真实 NAS 的客户端协议测试。"""

from __future__ import annotations

import unittest

from pywebdav.client import WebDAVClient, WebDAVError


class Response:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class Session:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> Response:
        self.calls.append((method, url, kwargs))
        return self.response


class WebDAVClientTest(unittest.TestCase):
    def test_paths_stay_below_webdav_root_and_are_encoded(self) -> None:
        client = WebDAVClient("https://nas.example/dav")
        self.assertEqual(client._url("照片/夏天 2026.jpg"), "https://nas.example/dav/%E7%85%A7%E7%89%87/%E5%A4%8F%E5%A4%A9%202026.jpg")
        with self.assertRaises(ValueError):
            client._url("../private")

    def test_cross_redirect_is_rejected_before_credentials_can_follow(self) -> None:
        client = WebDAVClient("https://nas.example/dav", "alice", "secret")
        client.session = Session(Response(302))  # type: ignore[assignment]
        with self.assertRaises(WebDAVError):
            client.exists("document.txt")
        self.assertFalse(client.session.calls[0][2]["allow_redirects"])

    def test_list_parses_directory_metadata(self) -> None:
        xml = b'''<multistatus xmlns="DAV:"><response><href>/dav/folder/</href><propstat><prop><resourcetype><collection/></resourcetype><getcontentlength>0</getcontentlength></prop></propstat></response></multistatus>'''
        client = WebDAVClient("https://nas.example/dav")
        client.session = Session(Response(207, xml))  # type: ignore[assignment]
        entries = client.list("/")
        self.assertEqual(entries[0].path, "/dav/folder/")
        self.assertTrue(entries[0].is_directory)


if __name__ == "__main__":
    unittest.main()
