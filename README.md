# TileMapService

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

高性能离线瓦片地图服务，支持读取 ESRI ArcGIS Compact Cache 并发布为标准瓦片服务（XYZ、TMS、WMTS）。

## 特性

### 核心功能
- 支持 ArcGIS Compact Cache V1/V2 格式
- 多坐标系：支持任意 EPSG 坐标系（EPSG:3857, EPSG:4326, EPSG:4490 等）
- 多请求方式：XYZ / TMS / Source Matrix / Geographic Matrix
- 图像格式：PNG / JPEG / 自动格式
- WMTS 1.0.0 标准协议支持

### 性能优化
- 分片锁缓存（Sharded Cache）- 16 分片，高并发优化
- Bundle 连接池 - 复用文件句柄，减少 IO 开销
- TTL + LRU 缓存策略

### 部署方式
- 打包目录（Windows/Linux x86_64/Linux aarch64）- onedir 模式，稳定可靠
- Linux systemd 开机自启动
- Docker 容器化部署
- Python 源码运行

---

## 快速开始

### 方式1: 打包目录（推荐）

**目录结构:**
```
TileMapService/
├── TileMapService.exe    # 主程序（Windows）
├── config.example.yaml   # 配置文件示例
├── static/               # 静态资源（Leaflet 预览）
└── ...                   # Python 运行时
```

**Windows:**
```powershell
cd TileMapService

# 创建配置文件
Copy-Item config.example.yaml config.yaml
# 编辑 config.yaml 设置数据源

# 运行
.\TileMapService.exe --port 8080
```

**Linux:**
```bash
cd TileMapService
chmod +x TileMapService

# 创建配置文件
cp config.example.yaml config.yaml
# 编辑 config.yaml 设置数据源

# 前台运行
./TileMapService --port 8080

# systemd 托管（开机自启）
sudo ./TileMapService service install --port 8080
```

访问预览页面: http://localhost:8080/preview

### 方式2: 源码运行

环境要求：Python 3.11+，推荐使用 [uv](https://github.com/astral-sh/uv)

```bash
# 安装依赖
uv sync

# 可选：安装包为可编辑模式（提升版本查询性能）
uv pip install -e .

# 查看版本
uv run python src/main.py --version

# 前台运行
uv run python src/main.py --port 8080

# Linux 后台托管请使用打包版本的 systemd 命令，或使用 nohup/systemctl 等系统工具
```

### 方式3: Docker

```bash
cd docker && docker compose up --build
# http://localhost:8000/preview
```

---

## 进程管理

### Daemon 模式（后台守护进程，仅 Windows）

Windows 支持 `start` / `status` / `stop` / `restart` 四个命令：

```powershell
.\TileMapService.exe start --port 8000
.\TileMapService.exe status
.\TileMapService.exe stop
.\TileMapService.exe restart --port 8000
```

**日志位置**：
- 守护进程日志：`logs/tilemapservice_YYYYMMDD_HHMMSS.log`
- 包含启动信息、运行日志、错误信息

**技术实现**：
- **Windows**：使用 `subprocess.Popen` + `CREATE_NO_WINDOW` 标志后台运行
- 支持优雅关闭，处理完当前请求后退出

### Linux 运行方式

Linux 不提供 daemon 子命令，请前台运行或用系统进程管理托管：

```bash
# 前台运行
./TileMapService --port 8000

# 后台托管（示例：nohup）
nohup ./TileMapService --port 8000 >/tmp/tilemapservice.log 2>&1 &

# systemd 托管（推荐用于生产）
sudo ./TileMapService service install --port 8000
./TileMapService service status
./TileMapService service logs -n 50
sudo ./TileMapService service restart
```

systemd 详细说明见 [`docs/SYSTEMD_GUIDE.md`](docs/SYSTEMD_GUIDE.md)。

---

## 配置

从示例文件创建配置文件：

```bash
cp config/config.example.yaml config/config.yaml
```

编辑 `config/config.yaml` 配置数据源：

```yaml
server:
  host: 0.0.0.0
  port: 8000
  graceful_shutdown_timeout: 5

cache:
  enabled: true
  max_size: 1000
  ttl: 3600
  num_shards: 16          # 分片数量（高并发优化）

bundle_pool:
  enabled: true           # Bundle 连接池
  max_size: 50            # 最大连接数

sources:
  - name: "my-tiles"
    path: "./data/tiles"
    description: "我的瓦片数据"
```

### Source 配置

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 数据源名称（URL 中使用） |
| `path` | string | ✅ | Compact Cache 根目录 |
| `spatial_ref.wkid` | int | ❌ | EPSG 代码（无 Conf.xml 时必需） |

---

## API 端点

### 预览界面
```
GET /preview              - 所有数据源预览
GET /preview/{source}     - 单个数据源预览
```

### 瓦片服务

**XYZ (Web Mercator):**
```
GET /tiles/{source}/{z}/{x}/{y}.png
GET /tiles/{source}/{z}/{x}/{y}.jpg
```

**TMS (Y轴反转):**
```
GET /tiles/{source}/tms/{z}/{x}/{y}.png
```

**CRS Matrix (源坐标系):**
```
GET /tiles/{source}/crs/epsg:{epsg}/{z}/{x}/{y}?matrix=source
GET /tiles/{source}/crs/epsg:4326/{z}/{x}/{y}?matrix=geographic
```

### WMTS 服务
```
GET /wmts?SERVICE=WMTS&REQUEST=GetCapabilities
GET /wmts/{source}/{TileMatrix}/{TileRow}/{TileCol}
```

### 元数据与监控
```
GET /api/sources          - 数据源列表
GET /api/sources/{name}   - 数据源详情（包含 tile_matrix CRS 元数据）
GET /api/stats            - 性能统计（缓存命中率、请求计数）
GET /health               - 健康检查
```

**API 响应字段说明**:
- `tile_info`: 瓦片方案、层级定义（向后兼容）
- `tile_matrix`: CRS 元数据（proj4、WKT、分辨率数组），支持任意 EPSG 预览
  - `crs`: EPSG 代码（如 "EPSG:4490"）
  - `proj4`: Proj4 定义字符串
  - `wkt`: WKT 定义
  - `is_geographic`: 布尔标志
  - `resolutions`: 各缩放级别的分辨率数组
  - `origin`: 瓦片原点坐标
  - `tile_size`: 瓦片尺寸（像素）

---

## 架构

### 请求流程
```
HTTP Request
    ↓
API Router (routes.py)
    ↓
TileService
    ├── TileLocator (坐标转换)
    ├── BundlePool (文件句柄复用)
    ├── BundleReader (V1/V2 格式读取)
    ├── ShardedCache (分片缓存)
    └── ImageFormatter (格式转换)
    ↓
Response
```

### 核心组件

```
tilemapservice/
├── api/                    # FastAPI 路由
│   ├── routes.py           # 路由注册
│   ├── tiles.py            # XYZ/TMS/CRS 瓦片
│   ├── wmts.py             # WMTS 服务
│   ├── wmts_exception.py   # WMTS 异常处理
│   ├── metadata.py         # 数据源元数据
│   ├── preview.py          # Leaflet 预览
│   └── stats.py            # 性能统计
│
├── services/               # 业务逻辑
│   ├── tile_service.py     # 瓦片服务编排
│   ├── tile_locator.py     # 坐标定位
│   ├── source_manager.py   # 数据源管理
│   ├── cache.py            # 基础缓存
│   ├── sharded_cache.py    # 分片锁缓存
│   ├── bundle_pool.py      # Bundle 连接池
│   ├── image_formatter.py  # 图像格式转换
│   ├── capabilities_builder.py  # WMTS Capabilities
│   └── wmts_service.py     # WMTS 服务逻辑
│
├── readers/                # 数据读取
│   ├── bundle_reader.py    # Compact Cache V1/V2
│   ├── conf_parser.py      # Conf.xml 解析
│   └── cdi_parser.py       # conf.cdi 解析
│
├── models/                 # 数据模型
│   ├── config.py           # 配置模型
│   ├── source.py           # 数据源模型
│   ├── tile.py             # 瓦片请求/响应
│   └── wmts.py             # WMTS 模型
│
└── utils/                  # 工具函数
    ├── coordinates.py      # 坐标转换
    ├── stats.py            # 统计追踪
    ├── logger.py           # 日志配置
    └── exceptions.py       # 异常定义
```

---

## 构建

使用 PyInstaller **onedir 模式**打包。

发布包汇总：

| 平台 | 输出包名 | 说明 |
| --- | --- | --- |
| Windows x86_64 | `TileMapService-v<version>-windows-x86_64.tar.gz` | Windows onedir 发布包 |
| Linux x86_64 | `TileMapService-v<version>-linux-x86_64.tar.gz` | Linux x86_64 onedir 发布包 |
| Linux aarch64 | `TileMapService-v<version>-linux-aarch64.tar.gz` | Linux ARM64/aarch64 onedir 发布包 |
| Linux StaticX x86_64 | `TileMapService-v<version>-linux-staticx-x86_64.tar.gz` | StaticX 单文件兼容包 |
| Linux StaticX aarch64 | `TileMapService-v<version>-linux-staticx-aarch64.tar.gz` | StaticX ARM64/aarch64 单文件兼容包 |

GitHub Actions 中，CI 负责运行测试；`main` 分支 push 或手动运行 workflow 时，可在 **Build Artifacts** 下载临时构建产物；推送 `v*` tag，或手动运行并输入已有 tag 时，会将对应包上传到 **GitHub Release**。

### Windows 构建
```powershell
uv sync --group build
uv run pyinstaller tilemapservice.spec --clean

# 输出: dist/TileMapService/
```

### Linux 构建（Docker）
```powershell
.\scripts\build-linux.ps1

# 输出: dist-linux/TileMapService/
```

### Linux StaticX 版本

使用 PyInstaller onefile + staticx 静态链接，兼容旧版 Linux：

```bash
.\scripts\build-linux-staticx.ps1  # Windows
./scripts/build-linux-staticx.sh   # Linux/macOS

# 输出: dist-static/TileMapService/
```

**特点**: 
- 单文件可执行 + 外置静态文件
- 所有依赖静态链接，无需系统库
- 兼容旧版 Linux（CentOS 7.0+, glibc 2.17+）
- 包含 PROJ 数据库支持坐标转换

详见 [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md)。

---

## 测试

```bash
uv run pytest tests/ -v
```

---

## 文档

- [`CLAUDE.md`](CLAUDE.md) - 项目架构（Claude Code）
- [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md) - 构建指南（Windows/Linux x86_64/Linux aarch64/staticx/GitHub Actions）
- [`docs/SYSTEMD_GUIDE.md`](docs/SYSTEMD_GUIDE.md) - Linux systemd 开机自启动指南

---

## 技术栈

- **FastAPI** - 异步 Web 框架
- **Uvicorn** - ASGI 服务器
- **Pillow** - 图像处理
- **pyproj** - 坐标转换
- **mercantile** - 瓦片计算
- **cachetools** - 缓存实现
- **Leaflet** - 地图预览
- **proj4js** - 坐标系转换（前端）
- **proj4leaflet** - Leaflet 任意 EPSG 支持

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
