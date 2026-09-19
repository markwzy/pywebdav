"""面向 NAS 的隐私优先 WebDAV 客户端。"""

from .client import File, WebDAVClient, WebDAVError

__all__ = ["File", "WebDAVClient", "WebDAVError"]
__version__ = "0.1.0"
