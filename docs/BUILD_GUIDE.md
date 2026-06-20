# TileMapService 构建指南

项目提供五类发布包：

| 平台/版本 | 构建脚本 | 输出压缩包 |
|---|---|---|
| Windows x86_64 onedir | `scripts/build-windows.ps1` | `TileMapService-v<version>-windows-x86_64.tar.gz` 或 `.zip` |
| Linux 标准版 onedir | `scripts/build-linux.ps1` / `scripts/build-linux.sh` | `TileMapService-v<version>-linux-x86_64.tar.gz` |
| Linux ARM64 标准版 onedir | GitHub Actions | `TileMapService-v<version>-linux-aarch64.tar.gz` |
| Linux staticx x86_64 兼容版 | `scripts/build-linux-staticx.ps1` / `scripts/build-linux-staticx.sh` | `TileMapService-v<version>-linux-staticx-x86_64.tar.gz` |
| Linux staticx ARM64 兼容版 | GitHub Actions | `TileMapService-v<version>-linux-staticx-aarch64.tar.gz` |

版本号来自 `pyproject.toml` 的 `project.version`。

---

## GitHub Actions 自动构建与发布

仓库提供 GitHub Actions 自动化工作流：

- CI：在推送和 Pull Request 中运行测试，验证代码与构建基础环境。
- Build Artifacts：手动构建发布包，可在 Actions 页面选择分支运行，用于验证某个分支的 Windows、Linux x86_64、Linux aarch64、Linux staticx x86_64 与 Linux staticx aarch64 包。
- Release workflow：正式发布工作流。推送版本 tag 后，从该 tag 重新检出并重新构建发布包，再上传到 GitHub Release，确保 Release 资产与 tag 内容一致。

正式发布示例：

```bash
git tag v0.1.1
git push origin v0.1.1
```

---

## Windows 构建

```powershell
uv sync --group build
.\scripts\build-windows.ps1
```

输出：
- `dist/TileMapService/`
- 根目录下的 `TileMapService-v<version>-windows-x86_64.tar.gz`，或在无 `tar` 时生成 `.zip`

本地验证：

```powershell
cd dist\TileMapService
.\TileMapService.exe --port 8080
```

---

## Linux 标准版构建

标准版使用 Docker 在 Debian 11 环境中构建 PyInstaller onedir 包，适合较新的 Linux 发行版。

```powershell
# Windows 主机
.\scripts\build-linux.ps1
```

```bash
# Linux/macOS 主机
./scripts/build-linux.sh
```

输出：
- `dist-linux/TileMapService/`
- 根目录下的 `TileMapService-v<version>-linux-x86_64.tar.gz`
- GitHub Actions 可构建 ARM64 标准版，输出 `TileMapService-v<version>-linux-aarch64.tar.gz`

兼容性：
- Ubuntu 20.04+
- Debian 11+
- CentOS Stream 9+
- Fedora 34+

---

## Linux staticx 兼容版构建

staticx 版本使用 PyInstaller onefile + staticx，适合 CentOS 7 / RHEL 7 等旧 glibc 环境。发布目录仍包含外置 `static/` 与 `config.example.yaml`。

```powershell
# Windows 主机
.\scripts\build-linux-staticx.ps1
```

```bash
# Linux/macOS 主机
./scripts/build-linux-staticx.sh
```

输出：
- `dist-static/TileMapService/`
- 根目录下的 `TileMapService-v<version>-linux-staticx-x86_64.tar.gz`
- GitHub Actions 可构建 ARM64 staticx 兼容版，输出 `TileMapService-v<version>-linux-staticx-aarch64.tar.gz`

兼容性：
- CentOS 7+
- RHEL 7+
- Ubuntu 16.04+
- Debian 8+

---

## 使用发布包

### Windows

```powershell
tar -xzf TileMapService-v<version>-windows-x86_64.tar.gz
cd TileMapService
Copy-Item config.example.yaml config.yaml
.\TileMapService.exe --port 8000
```

如果生成的是 `.zip`：

```powershell
Expand-Archive TileMapService-v<version>-windows-x86_64.zip
```

### Linux

```bash
tar -xzf TileMapService-v<version>-linux-x86_64.tar.gz
cd TileMapService
chmod +x TileMapService
cp config.example.yaml config.yaml
./TileMapService --port 8000
```

生产环境建议使用 systemd：

```bash
sudo ./TileMapService service install --port 8000
./TileMapService service status
./TileMapService service logs -n 50
```

详见 [`SYSTEMD_GUIDE.md`](SYSTEMD_GUIDE.md)。

---

## Docker 运行（不打包）

```bash
cd docker
docker compose up --build
```

或从项目根目录手动构建：

```bash
docker build -f docker/Dockerfile -t tilemapservice .
docker run -p 8000:8000 -v /path/to/data:/data tilemapservice
```

---

## 故障排查

### PyInstaller 未找到

```powershell
uv sync --group build
```

### 清理后重试打包

```powershell
Remove-Item build, dist -Recurse -Force
uv run pyinstaller tilemapservice.spec --clean
```

### Linux: `GLIBC_X.XX not found`

目标系统 glibc 过旧，请使用 Linux staticx 兼容版。

### Linux: `cannot execute binary file`

架构不匹配。当前脚本输出目标为 x86_64，请在匹配架构上运行或构建。
