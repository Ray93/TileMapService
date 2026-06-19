# TileMapService systemd 服务指南

适用于 Linux 生产部署（CentOS 7+、Ubuntu 16.04+、Debian 8+）。

## 快速开始

在**部署目录**下执行安装；该目录应包含 `TileMapService`、`config.example.yaml` 和 `static/`。

```bash
cd /opt/TileMapService
cp config.example.yaml config.yaml
# 编辑 config.yaml，配置数据源与服务参数

sudo ./TileMapService service install --port 8000
```

安装成功后会：
- 写入 `/etc/systemd/system/tilemapservice.service`
- 执行 `systemctl enable tilemapservice`
- 立即启动服务
- 将日志输出到 journald

## 验证

```bash
./TileMapService service status
./TileMapService service logs -n 50
curl http://localhost:8000/preview
systemctl is-enabled tilemapservice
```

## 常用管理命令

```bash
./TileMapService service status
./TileMapService service logs -n 50
./TileMapService service logs -f

sudo ./TileMapService service start
sudo ./TileMapService service stop
sudo ./TileMapService service restart
```

卸载：

```bash
sudo ./TileMapService service uninstall
```

也可以直接使用等价的 systemd 原生命令：

```bash
systemctl status tilemapservice
journalctl -u tilemapservice -f
sudo systemctl restart tilemapservice
```

## 参数说明

```bash
sudo ./TileMapService service install \
  --config config.yaml \
  --host 0.0.0.0 \
  --port 8000 \
  --user root
```

- `--config`：默认使用部署目录下的 `config.yaml`，写入 unit 时会转为绝对路径。
- `--host` / `--port`：仅显式指定时才写入 `ExecStart`，未指定时由 `config.yaml` 决定。
- `--user`：服务运行账号，默认 `root`；指定低权账号时必须先创建该用户并授予数据目录读权限。
- `--force`：已有 unit 时覆盖并重启。

> 当前版本暂不支持部署目录或配置路径含空格。

## 安全硬化示例

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin tilemap
sudo chown -R tilemap:tilemap /opt/TileMapService
sudo ./TileMapService service install --user tilemap --port 8000
```

unit 默认包含 `NoNewPrivileges=true`，并且不显式写 `Group=`，systemd 会使用该用户主组。

## 升级部署

```bash
cd /opt/TileMapService
# 替换二进制/静态文件，保留 config.yaml
sudo ./TileMapService service install --force
```

`--force` 会停止旧服务、清理 `tilemapservice` 的 failed 状态、覆盖 unit、执行 `daemon-reload` 并重启。

## 故障排查

启动失败：

```bash
journalctl -u tilemapservice -n 100
systemctl status tilemapservice
```

常见原因：
- 端口被前台实例占用
- `config.yaml` 不存在或配置错误
- 数据目录权限不足
- 部署目录不是有效发布目录（缺少 `config.example.yaml` 或 `static/`）
- 路径包含空格

重启风暴被限制后：

```bash
sudo systemctl reset-failed tilemapservice
sudo systemctl start tilemapservice
```

staticx 版本请确认 unit 未指向 `/tmp/staticx-*`：

```bash
systemctl cat tilemapservice | grep -E 'ExecStart|WorkingDirectory'
```
