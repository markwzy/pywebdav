"""pywebdav 命令行入口。"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from .client import WebDAVClient, WebDAVError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="隐私优先的 NAS WebDAV 客户端")
    parser.add_argument("--url", default=os.environ.get("WEBDAV_URL"), help="WebDAV 根地址，或 WEBDAV_URL")
    parser.add_argument("--username", default=os.environ.get("WEBDAV_USERNAME"), help="用户名，或 WEBDAV_USERNAME")
    parser.add_argument("--insecure", action="store_true", help="不校验 HTTPS 证书（仅限确认可信的自签名证书）")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ls").add_argument("remote", nargs="?", default="/")
    mkdir = subparsers.add_parser("mkdir")
    mkdir.add_argument("remote")
    mkdir.add_argument("--parents", action="store_true")
    upload = subparsers.add_parser("upload")
    upload.add_argument("local")
    upload.add_argument("remote")
    download = subparsers.add_parser("download")
    download.add_argument("remote")
    download.add_argument("local")
    subparsers.add_parser("delete").add_argument("remote")
    subparsers.add_parser("exists").add_argument("remote")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if not args.url:
        raise SystemExit("请通过 --url 或 WEBDAV_URL 提供 WebDAV 地址")
    password = os.environ.get("WEBDAV_PASSWORD")
    if args.username and password is None:
        password = getpass.getpass("WebDAV 密码: ")
    try:
        client = WebDAVClient(args.url, args.username, password, verify=not args.insecure)
        if args.command == "ls":
            for item in client.list(args.remote):
                kind = "目录" if item.is_directory else "文件"
                print(f"{kind}\t{item.size}\t{item.path}")
        elif args.command == "mkdir":
            client.mkdir(args.remote, parents=args.parents)
        elif args.command == "upload":
            client.upload(args.local, args.remote)
        elif args.command == "download":
            client.download(args.remote, args.local)
        elif args.command == "delete":
            client.delete(args.remote)
        else:
            print("存在" if client.exists(args.remote) else "不存在")
    except (OSError, WebDAVError, ValueError) as error:
        # 只输出操作错误，不回显 URL、用户名或密码，避免终端历史成为泄露面。
        print(f"操作失败：{error}", file=sys.stderr)
        raise SystemExit(1) from error
