"""WebDAV 协议客户端。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote, urljoin, urlparse
from xml.etree import ElementTree

import requests


DAV_NAMESPACE = "{DAV:}"
CHUNK_SIZE = 1024 * 1024


class WebDAVError(RuntimeError):
    """WebDAV 服务无法完成请求时抛出；异常中不包含认证信息。"""


@dataclass(frozen=True)
class File:
    """WebDAV 目录项元数据。"""

    path: str
    size: int
    modified: str | None
    created: str | None
    content_type: str | None
    is_directory: bool


class WebDAVClient:
    """仅连接创建时指定的单一 WebDAV 服务，防止凭据跨主机发送。"""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        *,
        verify: bool = True,
        timeout: float = 30,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url 必须是完整的 http 或 https 地址")
        if (username is None) != (password is None):
            raise ValueError("用户名和密码必须同时提供")

        # 统一尾随斜杠，后续相对路径只会落在此 WebDAV 根目录内。
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify
        if username is not None:
            self.session.auth = (username, password)

    def _url(self, path: str) -> str:
        # 按路径段编码而不是整体编码，避免文件名中的空格或中文改变 URL 语义。
        clean_path = path.lstrip("/")
        if any(part == ".." for part in clean_path.split("/")):
            # urljoin 会规范化 ..，可能使请求越出用户指定的 WebDAV 根目录。
            raise ValueError("远程路径不能包含 ..")
        return urljoin(self.base_url, quote(clean_path, safe="/%:@"))

    def _request(self, method: str, path: str, expected: int | tuple[int, ...], **kwargs: object) -> requests.Response:
        response = self.session.request(
            method,
            self._url(path),
            allow_redirects=False,
            timeout=self.timeout,
            **kwargs,
        )
        expected_codes = (expected,) if isinstance(expected, int) else expected
        if response.status_code in {301, 302, 307, 308}:
            # 不跟随重定向；requests 可能会在新地址继续使用会话认证信息。
            raise WebDAVError(f"{method} {path}: 服务要求重定向，已为保护凭据拒绝继续请求")
        if response.status_code not in expected_codes:
            raise WebDAVError(f"{method} {path}: 服务返回 HTTP {response.status_code}")
        return response

    def exists(self, path: str) -> bool:
        return self._request("HEAD", path, (200, 204, 404)).status_code != 404

    def mkdir(self, path: str, *, parents: bool = False) -> None:
        if not parents:
            self._request("MKCOL", path, (201, 405))
            return
        current = ""
        for part in (part for part in path.split("/") if part):
            current = f"{current}/{part}"
            self._request("MKCOL", current, (201, 405))

    def delete(self, path: str) -> None:
        self._request("DELETE", path, (200, 204))

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        with Path(local_path).open("rb") as source:
            self._put(source, remote_path)

    def _put(self, source: BinaryIO, remote_path: str) -> None:
        self._request("PUT", remote_path, (200, 201, 204), data=source)

    def download(self, remote_path: str, local_path: str | Path) -> None:
        # 只有服务确认成功才创建本地文件，避免错误响应覆盖用户已有文件。
        response = self._request("GET", remote_path, 200, stream=True)
        with Path(local_path).open("wb") as destination:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:
                    destination.write(chunk)

    def list(self, path: str = "/") -> list[File]:
        response = self._request("PROPFIND", path, 207, headers={"Depth": "1"})
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            raise WebDAVError("PROPFIND: 服务返回了无法解析的 XML") from error
        return [self._file_from_element(element) for element in root.findall(f"{DAV_NAMESPACE}response")]

    @staticmethod
    def _text(element: ElementTree.Element, name: str) -> str | None:
        node = element.find(f".//{DAV_NAMESPACE}{name}")
        return node.text if node is not None else None

    def _file_from_element(self, element: ElementTree.Element) -> File:
        size_text = self._text(element, "getcontentlength")
        resource_type = element.find(f".//{DAV_NAMESPACE}resourcetype/{DAV_NAMESPACE}collection")
        return File(
            path=self._text(element, "href") or "",
            size=int(size_text) if size_text and size_text.isdigit() else 0,
            modified=self._text(element, "getlastmodified"),
            created=self._text(element, "creationdate"),
            content_type=self._text(element, "getcontenttype"),
            is_directory=resource_type is not None,
        )
