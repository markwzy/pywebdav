"""将受限的 WebDAV 文件操作作为 MCP 工具提供给 Agent。"""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .client import WebDAVClient


LOCAL_ROOT_ENV = "PYWEBDAV_LOCAL_ROOT"


class NASOperations:
    """为 MCP 工具划定 NAS 根目录与本地工作目录两层边界。"""

    def __init__(self, client: WebDAVClient, local_root: Path) -> None:
        self.client = client
        self.local_root = local_root.resolve()

    @classmethod
    def from_environment(cls) -> NASOperations:
        """只在服务器进程读取凭据，避免将敏感信息作为工具参数交给 Agent。"""
        url = os.environ.get("WEBDAV_URL")
        username = os.environ.get("WEBDAV_USERNAME")
        password = os.environ.get("WEBDAV_PASSWORD")
        local_root_text = os.environ.get(LOCAL_ROOT_ENV)
        if not url:
            raise ValueError("必须设置 WEBDAV_URL")
        if not local_root_text:
            raise ValueError(f"必须设置 {LOCAL_ROOT_ENV}，用于限制 Agent 可访问的本地目录")

        local_root = Path(local_root_text).expanduser().resolve()
        if not local_root.is_dir():
            raise ValueError(f"{LOCAL_ROOT_ENV} 必须指向已存在的目录")
        return cls(WebDAVClient(url, username, password), local_root)

    def local_path(self, relative_path: str) -> Path:
        """拒绝绝对路径、父级跳转和符号链接逃逸，隔离 Agent 的本地文件权限。"""
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("本地路径必须是工作目录内、不含 .. 的相对路径")
        resolved = (self.local_root / candidate).resolve()
        if not resolved.is_relative_to(self.local_root):
            raise ValueError("本地路径不能通过符号链接离开工作目录")
        return resolved

    def list(self, path: str = "/") -> list[dict[str, object]]:
        return [asdict(item) for item in self.client.list(path)]

    def exists(self, path: str) -> bool:
        return self.client.exists(path)

    def mkdir(self, path: str, parents: bool = False) -> None:
        self.client.mkdir(path, parents=parents)

    def upload(self, local_path: str, remote_path: str, overwrite: bool = False) -> None:
        source = self.local_path(local_path)
        if not source.is_file():
            raise ValueError("上传源必须是本地工作目录中的普通文件")
        if not overwrite and self.client.exists(remote_path):
            raise ValueError("远程文件已存在；确认需要覆盖时请将 overwrite 设为 true")
        self.client.upload(source, remote_path)

    def download(self, remote_path: str, local_path: str, overwrite: bool = False) -> None:
        destination = self.local_path(local_path)
        if not destination.parent.is_dir():
            raise ValueError("本地目标目录不存在；请先在工作目录中创建它")
        if destination.exists() and not overwrite:
            raise ValueError("本地文件已存在；确认需要覆盖时请将 overwrite 设为 true")
        self.client.download(remote_path, destination)

    def delete(self, path: str) -> None:
        self.client.delete(path)


operations: NASOperations | None = None

mcp = FastMCP(
    "pywebdav-nas",
    instructions=(
        "此服务器只能操作启动时配置的单个 WebDAV 根目录，以及 PYWEBDAV_LOCAL_ROOT 指定的本地工作目录。"
        "先用 nas_list 或 nas_exists 确认目标；上传和下载默认拒绝覆盖，只有用户明确要求时才设置 overwrite=true。"
        "nas_delete 会永久删除远程项目，只能在用户明确指定删除目标后调用。不要请求或输出任何凭据。"
    ),
)


def _result(value: object) -> str:
    """使用 JSON 文本返回结构化结果，避免工具输出混入凭据或终端格式。"""
    return json.dumps(value, ensure_ascii=False)


def _operations() -> NASOperations:
    """延迟读取环境变量，使模块导入和单元测试不会依赖真实 NAS 配置。"""
    if operations is None:
        raise RuntimeError("MCP Server 尚未启动")
    return operations


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def nas_list(path: str = "/") -> str:
    """列出 NAS 目录；path 必须位于已配置的 WebDAV 根目录内。"""
    return _result(_operations().list(path))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def nas_exists(path: str) -> str:
    """检查 NAS 上的文件或目录是否存在。"""
    return _result({"exists": _operations().exists(path)})


@mcp.tool(annotations=ToolAnnotations(destructiveHint=False))
def nas_mkdir(path: str, parents: bool = False) -> str:
    """创建 NAS 目录；parents=true 时创建缺失的父目录。"""
    _operations().mkdir(path, parents)
    return _result({"created": path})


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def nas_upload(local_path: str, remote_path: str, overwrite: bool = False) -> str:
    """从受限本地工作目录上传文件；覆盖需要明确传入 overwrite=true。"""
    _operations().upload(local_path, remote_path, overwrite)
    return _result({"uploaded": remote_path})


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def nas_download(remote_path: str, local_path: str, overwrite: bool = False) -> str:
    """下载文件到受限本地工作目录；覆盖需要明确传入 overwrite=true。"""
    _operations().download(remote_path, local_path, overwrite)
    return _result({"downloaded": local_path})


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def nas_delete(path: str) -> str:
    """永久删除 NAS 上的文件或目录；仅可用于用户明确要求删除的目标。"""
    _operations().delete(path)
    return _result({"deleted": path})


def main() -> None:
    """以 stdio 方式运行，供 Codex 等本地 MCP 客户端连接。"""
    global operations
    operations = NASOperations.from_environment()
    mcp.run(transport="stdio")
