# pywebdav

一个用于 NAS 的轻量 WebDAV 命令行客户端，支持列目录、上传、下载、创建目录和删除。

## 安装

```bash
pip install "git+https://github.com/markwzy/pywebdav.git"
```

从源码安装：

```bash
pip install .
```

## 使用

将连接地址和账户信息放在当前终端环境中。工具不读取或写入配置文件，不记录请求内容，也不会上传任何使用数据。

```bash
export WEBDAV_URL="https://nas.example.com:5006/webdav"
export WEBDAV_USERNAME="your-name"
export WEBDAV_PASSWORD="your-password"

pywebdav ls /
pywebdav mkdir /documents
pywebdav upload ./photo.jpg /documents/photo.jpg
pywebdav download /documents/photo.jpg ./photo.jpg
pywebdav delete /documents/photo.jpg
```

也可以在单次命令中传入连接地址：

```bash
pywebdav --url https://nas.example.com/webdav --username your-name ls /
```

未提供密码时，程序会在终端安全询问。生产环境请保持 TLS 证书校验；仅在自签名证书已被确认可信时才使用 `--insecure`。

## Python 代码使用

应用程序可直接使用 `WebDAVClient`。建议仍通过环境变量提供凭据，避免把密码写入源码或提交到 Git。

```python
import os

from pywebdav import WebDAVClient, WebDAVError

client = WebDAVClient(
    os.environ["WEBDAV_URL"],
    os.environ["WEBDAV_USERNAME"],
    os.environ["WEBDAV_PASSWORD"],
)

try:
    # 列出目录；每项包含 path、size、modified 和 is_directory 等属性。
    for item in client.list("/documents"):
        print("目录" if item.is_directory else "文件", item.path, item.size)

    client.mkdir("/documents/photos", parents=True)
    client.upload("./photo.jpg", "/documents/photos/photo.jpg")
    client.download("/documents/photos/photo.jpg", "./downloaded-photo.jpg")
finally:
    # 会话仅存在于当前进程；显式关闭可及时释放连接。
    client.session.close()
```

服务端返回非预期状态时会抛出 `WebDAVError`，可按需处理：

```python
try:
    client.delete("/documents/photos/old-photo.jpg")
except WebDAVError as error:
    print(f"删除失败：{error}")
```

## 隐私与安全

- 凭据仅保存在本次进程内，不写入磁盘、不输出到终端。
- 不包含遥测、分析或自动联网功能；只会连接你指定的 WebDAV 地址。
- WebDAV 请求拒绝跟随跨域重定向，避免认证头被带往意外站点。
- 默认校验 HTTPS 证书。
