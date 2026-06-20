# GitHub Actions 与 ARM64 Linux 发布设计

## 背景

TileMapService 当前已有本地打包能力：

- Windows x86_64：`scripts/build-windows.ps1`
- Linux x86_64 标准 onedir：`scripts/build-linux.ps1` / `scripts/build-linux.sh`
- Linux x86_64 staticx 兼容版：`scripts/build-linux-staticx.ps1` / `scripts/build-linux-staticx.sh`

项目当前没有 `.github/workflows`。本设计在现有构建方式基础上新增 GitHub Actions 流水线，并增加 Linux ARM64（aarch64）标准包和 staticx 包发布能力。

## 目标

实现三类流水线：

1. CI：在 push、pull request、手动触发时运行测试。
2. Artifacts 构建：在 main push 或手动触发时构建所有发布包并上传 Actions artifacts。
3. Release 发布：在 `v*` tag push 时构建正式包，创建或更新 GitHub Release，并上传所有发布资产。

新增发布包：

- `TileMapService-v<version>-linux-aarch64.tar.gz`
- `TileMapService-v<version>-linux-staticx-aarch64.tar.gz`

保留现有发布包：

- `TileMapService-v<version>-windows-x86_64.tar.gz`
- `TileMapService-v<version>-linux-x86_64.tar.gz`
- `TileMapService-v<version>-linux-staticx-x86_64.tar.gz`

## 非目标

- 不修改 TileMapService 运行时逻辑、API、配置格式或服务行为。
- 不移除或改变现有本地打包入口。
- 不引入自托管 ARM64 runner。
- 不在本次工作中扩展本地 PowerShell/Bash 脚本的一键 ARM64 构建入口；ARM64 构建主要由 GitHub Actions 驱动。

## 流水线结构

新增 `.github/workflows` 下三个 workflow。

### `ci.yml`

触发条件：

- `push`
- `pull_request`
- `workflow_dispatch`

行为：

- 安装 Python 与 uv。
- 同步依赖。
- 运行 `uv run pytest tests/ -v`。

目的：

- 保证代码质量。
- 与打包发布解耦。

### `build-artifacts.yml`

触发条件：

- `push` 到 `main`
- `workflow_dispatch`

手动触发说明：

- GitHub Actions 的 `workflow_dispatch` 可在 GitHub 页面选择任意包含该 workflow 文件的分支运行。
- 手动触发的 artifacts 表示对应分支和 commit 的构建结果，不代表正式 Release。

行为：

- 独立构建并上传以下 artifacts：
  - Windows x86_64
  - Linux x86_64 标准版
  - Linux x86_64 staticx
  - Linux aarch64 标准版
  - Linux aarch64 staticx

### `release.yml`

触发条件：

- `push` tag：`v*`
- 可保留 `workflow_dispatch`，但要求显式输入 tag/ref，避免误把普通分支发布成正式 Release。

行为：

- 从 tag 对应源码重新构建全部正式包。
- 所有包构建成功后创建或更新 GitHub Release。
- 上传所有 Release assets。

设计理由：

- 不复用 main 分支 artifacts，避免 Release 产物与 tag 源码不一致。
- tag 与产物强绑定，便于追溯。

## 构建脚本设计

保留现有用户入口：

- `scripts/build-windows.ps1`
- `scripts/build-linux.ps1`
- `scripts/build-linux.sh`
- `scripts/build-linux-staticx.ps1`
- `scripts/build-linux-staticx.sh`

新增 GitHub Actions 专用脚本：

- `scripts/ci-build-linux.sh <variant> <arch>`

参数：

- `variant`
  - `standard`
  - `staticx`
- `arch`
  - `x86_64`
  - `aarch64`

示例：

```bash
./scripts/ci-build-linux.sh standard x86_64
./scripts/ci-build-linux.sh standard aarch64
./scripts/ci-build-linux.sh staticx x86_64
./scripts/ci-build-linux.sh staticx aarch64
```

脚本职责：

- 将 `x86_64` 映射为 Docker platform `linux/amd64`。
- 将 `aarch64` 映射为 Docker platform `linux/arm64`。
- 选择 Dockerfile：
  - `standard` 使用 `docker/Dockerfile.linux`
  - `staticx` 使用 `docker/Dockerfile.staticx`
- 传入用于包名的架构标识。
- 运行 buildx 构建。
- 将构建产物复制到可上传目录。

## Docker/ARM64 构建设计

ARM64 不做 PyInstaller 交叉编译。构建方式是在目标架构容器中运行 PyInstaller：

- x86_64：`docker buildx build --platform linux/amd64`
- aarch64：`docker buildx build --platform linux/arm64`

GitHub Actions 中启用：

- `docker/setup-qemu-action`
- `docker/setup-buildx-action`

修改 Dockerfile：

- `docker/Dockerfile.linux`
- `docker/Dockerfile.staticx`

新增 build arg：

- `TARGETARCH_NAME`

用于输出包命名：

- `linux-x86_64`
- `linux-aarch64`
- `linux-staticx-x86_64`
- `linux-staticx-aarch64`

## 发布资产命名

版本号继续来自 `pyproject.toml` 的 `project.version`。

正式产物命名：

```text
TileMapService-v<version>-windows-x86_64.tar.gz
TileMapService-v<version>-linux-x86_64.tar.gz
TileMapService-v<version>-linux-staticx-x86_64.tar.gz
TileMapService-v<version>-linux-aarch64.tar.gz
TileMapService-v<version>-linux-staticx-aarch64.tar.gz
```

## 错误处理

- Shell 脚本使用 `set -euo pipefail`。
- 单个构建 job 失败时，该 job 失败并使 workflow 失败。
- Artifacts workflow 中，已成功 job 的 artifacts 仍可从运行记录查看。
- Release workflow 中，只有所有构建 job 成功后才创建或更新 Release。
- Release asset 重跑时应支持恢复：采用覆盖上传，或先删除同名 asset 后重新上传。

## 验证策略

CI 验证：

```bash
uv sync
uv run pytest tests/ -v
```

打包验证：

- 检查每个期望的压缩包存在。
- Windows 包由 `windows-latest` runner 构建。
- Linux x86_64 和 Linux aarch64 包由 Docker buildx 构建。
- ARM64 二进制不在 x86_64 runner 上直接执行；第一版只验证 Docker 构建成功和包结构产出。
- Linux x86_64 在本设计第一版不执行 `./TileMapService --version` smoke test，以保持 workflow 简单且与 ARM64 验证策略一致。

## 文档更新

更新：

- `docs/BUILD_GUIDE.md`
- `README.md`

内容包括：

- GitHub Actions 触发方式。
- main artifacts 与 tag Release 的区别。
- 新增 ARM64 标准版和 staticx 兼容版包名。
- 本地构建命令仍保持不变。

## 最终改动范围

新增：

- `.github/workflows/ci.yml`
- `.github/workflows/build-artifacts.yml`
- `.github/workflows/release.yml`
- `scripts/ci-build-linux.sh`

修改：

- `docker/Dockerfile.linux`
- `docker/Dockerfile.staticx`
- `docs/BUILD_GUIDE.md`
- `README.md`

不修改：

- 应用运行时逻辑。
- API 路由。
- 配置模型。
- 测试数据与样例数据。
