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

## 隐私与安全

- 凭据仅保存在本次进程内，不写入磁盘、不输出到终端。
- 不包含遥测、分析或自动联网功能；只会连接你指定的 WebDAV 地址。
- WebDAV 请求拒绝跟随跨域重定向，避免认证头被带往意外站点。
- 默认校验 HTTPS 证书。
