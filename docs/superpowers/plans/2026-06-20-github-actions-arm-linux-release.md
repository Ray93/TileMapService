# GitHub Actions ARM Linux Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions CI, main-branch artifact builds, tag-driven GitHub Releases, and Linux aarch64 standard/staticx package publishing.

**Architecture:** Keep application code unchanged. Add three focused workflows, one CI Linux build helper, and parameterize the existing Linux Docker packaging images so the same build path can produce x86_64 and aarch64 artifacts.

**Tech Stack:** GitHub Actions, uv, PyInstaller, Docker Buildx, QEMU, Bash, PowerShell, Python 3.11.

---

## File Structure

- Create `.github/workflows/ci.yml`: test-only workflow for push, pull request, and manual runs.
- Create `.github/workflows/build-artifacts.yml`: main/manual package workflow that uploads Actions artifacts.
- Create `.github/workflows/release.yml`: tag/manual package workflow that creates or updates GitHub Releases.
- Create `scripts/ci-build-linux.sh`: Linux CI helper for standard/staticx and x86_64/aarch64 builds.
- Modify `docker/Dockerfile.linux`: add `TARGETARCH_NAME` build arg and architecture-aware archive naming.
- Modify `docker/Dockerfile.staticx`: add `TARGETARCH_NAME` build arg and architecture-aware archive naming.
- Modify `docs/BUILD_GUIDE.md`: document GitHub Actions workflows and ARM64 packages.
- Modify `README.md`: summarize new published package set and workflow behavior.

---

### Task 1: Add CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write workflow file**

Create `.github/workflows/ci.yml` with this exact content:

```yaml
name: CI

on:
  push:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up uv
        uses: astral-sh/setup-uv@v5

      - name: Sync dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest tests/ -v
```

- [ ] **Step 2: Verify YAML file exists**

Run:

```powershell
Test-Path .github\workflows\ci.yml
Get-Content .github\workflows\ci.yml
```

Expected: `True`, followed by the workflow content above.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add test workflow"
```

---

### Task 2: Add Linux CI Build Helper

**Files:**
- Create: `scripts/ci-build-linux.sh`

- [ ] **Step 1: Write Linux build helper**

Create `scripts/ci-build-linux.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <standard|staticx> <x86_64|aarch64>" >&2
    exit 2
fi

variant="$1"
arch="$2"

case "$arch" in
    x86_64)
        platform="linux/amd64"
        ;;
    aarch64)
        platform="linux/arm64"
        ;;
    *)
        echo "Unsupported arch: $arch" >&2
        exit 2
        ;;
esac

case "$variant" in
    standard)
        dockerfile="docker/Dockerfile.linux"
        suffix="linux-${arch}"
        ;;
    staticx)
        dockerfile="docker/Dockerfile.staticx"
        suffix="linux-staticx-${arch}"
        ;;
    *)
        echo "Unsupported variant: $variant" >&2
        exit 2
        ;;
esac

version="$(python3 - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"

image="tilemapservice-${variant}-${arch}:ci"
output_dir="dist-ci/${variant}-${arch}"
expected_archive="${output_dir}/TileMapService-v${version}-${suffix}.tar.gz"

echo "========================================"
echo "  TileMapService Linux CI Build"
echo "========================================"
echo "Variant:  ${variant}"
echo "Arch:     ${arch}"
echo "Platform: ${platform}"
echo "Version:  ${version}"
echo "Output:   ${expected_archive}"
echo ""

rm -rf "${output_dir}"
mkdir -p "${output_dir}" artifacts

docker buildx build \
    --platform "${platform}" \
    --build-arg "TARGETARCH_NAME=${arch}" \
    --load \
    -t "${image}" \
    -f "${dockerfile}" \
    .

docker run --rm \
    -v "$(pwd)/${output_dir}:/output" \
    "${image}"

if [[ ! -f "${expected_archive}" ]]; then
    echo "Expected archive not found: ${expected_archive}" >&2
    echo "Files produced under ${output_dir}:" >&2
    find "${output_dir}" -maxdepth 3 -type f -print >&2 || true
    exit 1
fi

cp "${expected_archive}" artifacts/
echo "Created artifact: artifacts/$(basename "${expected_archive}")"
```

- [ ] **Step 2: Verify helper rejects invalid input**

Run:

```powershell
bash scripts/ci-build-linux.sh
```

Expected: exit code `2` and usage text:

```text
Usage: scripts/ci-build-linux.sh <standard|staticx> <x86_64|aarch64>
```

- [ ] **Step 3: Commit**

```bash
git add scripts/ci-build-linux.sh
git commit -m "build: add linux ci package helper"
```

---

### Task 3: Parameterize Standard Linux Docker Package Naming

**Files:**
- Modify: `docker/Dockerfile.linux`

- [ ] **Step 1: Add build arg after `FROM`**

Change the top of `docker/Dockerfile.linux` from:

```dockerfile
FROM python:3.11-slim-bullseye
```

to:

```dockerfile
FROM python:3.11-slim-bullseye

ARG TARGETARCH_NAME=x86_64
```

- [ ] **Step 2: Update archive creation command**

Replace this block:

```dockerfile
RUN cp config/config.example.yaml dist/TileMapService/config.example.yaml && \
    VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])") && \
    tar -czf /app/TileMapService-v${VERSION}-linux-x86_64.tar.gz -C dist TileMapService
```

with:

```dockerfile
RUN cp config/config.example.yaml dist/TileMapService/config.example.yaml && \
    VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])") && \
    tar -czf /app/TileMapService-v${VERSION}-linux-${TARGETARCH_NAME}.tar.gz -C dist TileMapService
```

- [ ] **Step 3: Update default command archive glob**

Replace this line:

```dockerfile
CMD ["sh", "-c", "ARCHIVE=$(ls /app/TileMapService-v*-linux-x86_64.tar.gz | head -n 1) && cp -r dist/TileMapService /output/ && cp \"$ARCHIVE\" /output/ && echo \"Build complete! Directory: TileMapService/ | Archive: $(basename \"$ARCHIVE\")\""]
```

with:

```dockerfile
CMD ["sh", "-c", "ARCHIVE=$(ls /app/TileMapService-v*-linux-*.tar.gz | head -n 1) && cp -r dist/TileMapService /output/ && cp \"$ARCHIVE\" /output/ && echo \"Build complete! Directory: TileMapService/ | Archive: $(basename \"$ARCHIVE\")\""]
```

- [ ] **Step 4: Verify Dockerfile contains parameterized archive name**

Run:

```powershell
Select-String -Path docker\Dockerfile.linux -Pattern 'ARG TARGETARCH_NAME|linux-\$\{TARGETARCH_NAME\}|linux-\*.tar.gz'
```

Expected: all three patterns are present.

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile.linux
git commit -m "build: parameterize linux package architecture"
```

---

### Task 4: Parameterize Staticx Linux Docker Package Naming

**Files:**
- Modify: `docker/Dockerfile.staticx`

- [ ] **Step 1: Add build arg after `FROM`**

Change the top of `docker/Dockerfile.staticx` from:

```dockerfile
FROM python:3.11-slim-bullseye AS builder
```

to:

```dockerfile
FROM python:3.11-slim-bullseye AS builder

ARG TARGETARCH_NAME=x86_64
```

- [ ] **Step 2: Update staticx archive creation command**

Replace this block:

```dockerfile
RUN VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])") && \
    tar -czf /app/TileMapService-v${VERSION}-linux-staticx-x86_64.tar.gz -C dist TileMapService
```

with:

```dockerfile
RUN VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])") && \
    tar -czf /app/TileMapService-v${VERSION}-linux-staticx-${TARGETARCH_NAME}.tar.gz -C dist TileMapService
```

- [ ] **Step 3: Update default command archive glob**

Replace this line:

```dockerfile
CMD ["sh", "-c", "ARCHIVE=$(ls /app/TileMapService-v*-linux-staticx-x86_64.tar.gz | head -n 1) && cp -r /app/dist/TileMapService /output/TileMapService && cp \"$ARCHIVE\" /output/ && echo \"Static build complete! onefile + staticx with external static files. Linux runs foreground (no fork). Compatible with CentOS 7.0+ (glibc 2.17+) | Directory: TileMapService/ | Archive: $(basename \"$ARCHIVE\")\""]
```

with:

```dockerfile
CMD ["sh", "-c", "ARCHIVE=$(ls /app/TileMapService-v*-linux-staticx-*.tar.gz | head -n 1) && cp -r /app/dist/TileMapService /output/TileMapService && cp \"$ARCHIVE\" /output/ && echo \"Static build complete! onefile + staticx with external static files. Linux runs foreground (no fork). Compatible with CentOS 7.0+ (glibc 2.17+) | Directory: TileMapService/ | Archive: $(basename \"$ARCHIVE\")\""]
```

- [ ] **Step 4: Verify Dockerfile contains parameterized staticx archive name**

Run:

```powershell
Select-String -Path docker\Dockerfile.staticx -Pattern 'ARG TARGETARCH_NAME|linux-staticx-\$\{TARGETARCH_NAME\}|linux-staticx-\*.tar.gz'
```

Expected: all three patterns are present.

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile.staticx
git commit -m "build: parameterize staticx package architecture"
```

---

### Task 5: Add Main/Manual Artifacts Workflow

**Files:**
- Create: `.github/workflows/build-artifacts.yml`

- [ ] **Step 1: Write artifacts workflow**

Create `.github/workflows/build-artifacts.yml` with this exact content:

```yaml
name: Build Artifacts

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  windows-x86_64:
    name: Windows x86_64
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up uv
        uses: astral-sh/setup-uv@v5

      - name: Build Windows package
        shell: pwsh
        run: .\scripts\build-windows.ps1

      - name: Collect Windows package
        shell: pwsh
        run: |
          New-Item -ItemType Directory -Path artifacts -Force | Out-Null
          $archive = Get-ChildItem -Path . -Filter 'TileMapService-v*-windows-x86_64.tar.gz' | Select-Object -First 1
          if (-not $archive) {
            Write-Error 'Windows archive not found'
          }
          Copy-Item $archive.FullName -Destination artifacts

      - name: Upload Windows package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-windows-x86_64
          path: artifacts/TileMapService-v*-windows-x86_64.tar.gz
          retention-days: 14
          if-no-files-found: error

  linux-x86_64:
    name: Linux x86_64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux x86_64 package
        run: bash scripts/ci-build-linux.sh standard x86_64

      - name: Upload Linux x86_64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-x86_64
          path: artifacts/TileMapService-v*-linux-x86_64.tar.gz
          retention-days: 14
          if-no-files-found: error

  linux-staticx-x86_64:
    name: Linux staticx x86_64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux staticx x86_64 package
        run: bash scripts/ci-build-linux.sh staticx x86_64

      - name: Upload Linux staticx x86_64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-staticx-x86_64
          path: artifacts/TileMapService-v*-linux-staticx-x86_64.tar.gz
          retention-days: 14
          if-no-files-found: error

  linux-aarch64:
    name: Linux aarch64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux aarch64 package
        run: bash scripts/ci-build-linux.sh standard aarch64

      - name: Upload Linux aarch64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-aarch64
          path: artifacts/TileMapService-v*-linux-aarch64.tar.gz
          retention-days: 14
          if-no-files-found: error

  linux-staticx-aarch64:
    name: Linux staticx aarch64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux staticx aarch64 package
        run: bash scripts/ci-build-linux.sh staticx aarch64

      - name: Upload Linux staticx aarch64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-staticx-aarch64
          path: artifacts/TileMapService-v*-linux-staticx-aarch64.tar.gz
          retention-days: 14
          if-no-files-found: error
```

- [ ] **Step 2: Verify workflow contains all five upload names**

Run:

```powershell
Select-String -Path .github\workflows\build-artifacts.yml -Pattern 'tilemapservice-windows-x86_64|tilemapservice-linux-x86_64|tilemapservice-linux-staticx-x86_64|tilemapservice-linux-aarch64|tilemapservice-linux-staticx-aarch64'
```

Expected: five matching artifact names.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build-artifacts.yml
git commit -m "ci: add package artifact workflow"
```

---

### Task 6: Add Tag/Manual Release Workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write release workflow**

Create `.github/workflows/release.yml` with this exact content:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:
    inputs:
      tag:
        description: "Existing tag to release, for example v0.1.1"
        required: true
        type: string

permissions:
  contents: read

jobs:
  windows-x86_64:
    name: Windows x86_64
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up uv
        uses: astral-sh/setup-uv@v5

      - name: Build Windows package
        shell: pwsh
        run: .\scripts\build-windows.ps1

      - name: Collect Windows package
        shell: pwsh
        run: |
          New-Item -ItemType Directory -Path artifacts -Force | Out-Null
          $archive = Get-ChildItem -Path . -Filter 'TileMapService-v*-windows-x86_64.tar.gz' | Select-Object -First 1
          if (-not $archive) {
            Write-Error 'Windows archive not found'
          }
          Copy-Item $archive.FullName -Destination artifacts

      - name: Upload Windows package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-windows-x86_64
          path: artifacts/TileMapService-v*-windows-x86_64.tar.gz
          if-no-files-found: error

  linux-x86_64:
    name: Linux x86_64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux x86_64 package
        run: bash scripts/ci-build-linux.sh standard x86_64

      - name: Upload Linux x86_64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-x86_64
          path: artifacts/TileMapService-v*-linux-x86_64.tar.gz
          if-no-files-found: error

  linux-staticx-x86_64:
    name: Linux staticx x86_64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux staticx x86_64 package
        run: bash scripts/ci-build-linux.sh staticx x86_64

      - name: Upload Linux staticx x86_64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-staticx-x86_64
          path: artifacts/TileMapService-v*-linux-staticx-x86_64.tar.gz
          if-no-files-found: error

  linux-aarch64:
    name: Linux aarch64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux aarch64 package
        run: bash scripts/ci-build-linux.sh standard aarch64

      - name: Upload Linux aarch64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-aarch64
          path: artifacts/TileMapService-v*-linux-aarch64.tar.gz
          if-no-files-found: error

  linux-staticx-aarch64:
    name: Linux staticx aarch64
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref }}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Linux staticx aarch64 package
        run: bash scripts/ci-build-linux.sh staticx aarch64

      - name: Upload Linux staticx aarch64 package
        uses: actions/upload-artifact@v4
        with:
          name: tilemapservice-linux-staticx-aarch64
          path: artifacts/TileMapService-v*-linux-staticx-aarch64.tar.gz
          if-no-files-found: error

  publish:
    name: Publish GitHub Release
    runs-on: ubuntu-latest
    needs:
      - windows-x86_64
      - linux-x86_64
      - linux-staticx-x86_64
      - linux-aarch64
      - linux-staticx-aarch64
    permissions:
      contents: write

    steps:
      - name: Resolve release tag
        id: release-tag
        shell: bash
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            tag="${{ inputs.tag }}"
          else
            tag="${GITHUB_REF_NAME}"
          fi

          if [[ ! "${tag}" =~ ^v[0-9] ]]; then
            echo "Release tag must start with v followed by a digit, got: ${tag}" >&2
            exit 1
          fi

          echo "tag=${tag}" >> "${GITHUB_OUTPUT}"

      - name: Download package artifacts
        uses: actions/download-artifact@v4
        with:
          pattern: tilemapservice-*
          path: release-assets
          merge-multiple: true

      - name: List release assets
        run: ls -la release-assets

      - name: Create or update GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.release-tag.outputs.tag }}
          name: TileMapService ${{ steps.release-tag.outputs.tag }}
          files: release-assets/TileMapService-v*.tar.gz
          fail_on_unmatched_files: true
          overwrite_files: true
```

- [ ] **Step 2: Verify publish job depends on all package jobs**

Run:

```powershell
Select-String -Path .github\workflows\release.yml -Pattern 'windows-x86_64|linux-x86_64|linux-staticx-x86_64|linux-aarch64|linux-staticx-aarch64|softprops/action-gh-release'
```

Expected: all package job names and release action reference are present.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow"
```

---

### Task 7: Update Build Documentation

**Files:**
- Modify: `docs/BUILD_GUIDE.md`

- [ ] **Step 1: Update package table**

Replace the existing package table under `# TileMapService 构建指南` with:

```markdown
项目提供五类发布包：

| 平台/版本 | 构建方式 | 输出压缩包 |
|---|---|---|
| Windows onedir x86_64 | `scripts/build-windows.ps1` 或 GitHub Actions | `TileMapService-v<version>-windows-x86_64.tar.gz` |
| Linux 标准版 onedir x86_64 | `scripts/build-linux.ps1` / `scripts/build-linux.sh` 或 GitHub Actions | `TileMapService-v<version>-linux-x86_64.tar.gz` |
| Linux 标准版 onedir aarch64 | GitHub Actions | `TileMapService-v<version>-linux-aarch64.tar.gz` |
| Linux staticx 兼容版 x86_64 | `scripts/build-linux-staticx.ps1` / `scripts/build-linux-staticx.sh` 或 GitHub Actions | `TileMapService-v<version>-linux-staticx-x86_64.tar.gz` |
| Linux staticx 兼容版 aarch64 | GitHub Actions | `TileMapService-v<version>-linux-staticx-aarch64.tar.gz` |
```

- [ ] **Step 2: Add GitHub Actions section after version sentence**

Insert this section after `版本号来自 pyproject.toml 的 project.version。`:

```markdown
---

## GitHub Actions 自动构建与发布

仓库包含三条流水线：

- `CI`：`push`、`pull_request`、手动触发时运行 `uv run pytest tests/ -v`。
- `Build Artifacts`：推送到 `main` 或手动触发时构建所有平台包，并上传为 Actions artifacts。
- `Release`：推送 `v*` tag 或手动输入已有 tag 时构建正式包，创建或更新 GitHub Release，并上传所有发布资产。

手动触发 `Build Artifacts` 时，可以在 GitHub Actions 页面选择任意包含 workflow 文件的分支运行。该结果只表示对应分支和 commit 的测试包，不代表正式 Release。

正式发布建议使用 tag：

```bash
git tag v0.1.1
git push origin v0.1.1
```

Release workflow 会从 tag 对应源码重新构建产物，不复用 main 分支 artifacts。
```

- [ ] **Step 3: Add ARM64 note in Linux build section**

After the Linux standard build output list, add:

```markdown
GitHub Actions 还会通过 Docker Buildx + QEMU 构建 ARM64 标准版：

- `TileMapService-v<version>-linux-aarch64.tar.gz`
```

- [ ] **Step 4: Add ARM64 note in staticx section**

After the staticx output list, add:

```markdown
GitHub Actions 还会通过 Docker Buildx + QEMU 构建 ARM64 staticx 兼容版：

- `TileMapService-v<version>-linux-staticx-aarch64.tar.gz`
```

- [ ] **Step 5: Verify documentation mentions ARM64 artifacts**

Run:

```powershell
Select-String -Path docs\BUILD_GUIDE.md -Pattern 'linux-aarch64|linux-staticx-aarch64|Build Artifacts|Release workflow'
```

Expected: matches for both ARM64 artifact names and both workflow descriptions.

- [ ] **Step 6: Commit**

```bash
git add docs/BUILD_GUIDE.md
git commit -m "docs: document github actions packaging"
```

---

### Task 8: Update README Build Summary

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update deployment feature bullet**

Change:

```markdown
- 打包目录（Windows/Linux）- onedir 模式，稳定可靠
```

to:

```markdown
- 打包目录（Windows/Linux x86_64/Linux aarch64）- onedir 模式，稳定可靠
```

- [ ] **Step 2: Add release packages subsection before `### Windows 构建`**

Under `## 构建`, after `使用 PyInstaller **onedir 模式**打包。`, insert:

```markdown
发布包由本地脚本和 GitHub Actions 共同支持：

| 平台/版本 | 输出压缩包 |
|---|---|
| Windows x86_64 | `TileMapService-v<version>-windows-x86_64.tar.gz` |
| Linux x86_64 | `TileMapService-v<version>-linux-x86_64.tar.gz` |
| Linux aarch64 | `TileMapService-v<version>-linux-aarch64.tar.gz` |
| Linux staticx x86_64 | `TileMapService-v<version>-linux-staticx-x86_64.tar.gz` |
| Linux staticx aarch64 | `TileMapService-v<version>-linux-staticx-aarch64.tar.gz` |

GitHub Actions 行为：

- `CI`：push、pull request、手动触发时运行测试。
- `Build Artifacts`：main 分支 push 或手动触发时上传 Actions artifacts。
- `Release`：推送 `v*` tag 时创建或更新 GitHub Release。
```

- [ ] **Step 3: Update docs link wording**

Change:

```markdown
- [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md) - 构建指南（Windows/Linux/staticx）
```

to:

```markdown
- [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md) - 构建指南（Windows/Linux x86_64/Linux aarch64/staticx/GitHub Actions）
```

- [ ] **Step 4: Verify README mentions new packages**

Run:

```powershell
Select-String -Path README.md -Pattern 'linux-aarch64|linux-staticx-aarch64|Build Artifacts|GitHub Actions'
```

Expected: matches for both ARM64 artifact names and GitHub Actions workflow text.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: summarize automated release packages"
```

---

### Task 9: Local Verification

**Files:**
- Read: all files changed by previous tasks

- [ ] **Step 1: Check working tree**

Run:

```powershell
git status --short
```

Expected: no uncommitted files.

- [ ] **Step 2: Run test suite**

Run:

```powershell
uv run pytest tests/ -v
```

Expected: all non-integration tests pass.

- [ ] **Step 3: Verify CI helper invalid-input behavior**

Run:

```powershell
bash scripts/ci-build-linux.sh invalid x86_64
```

Expected: exit code `2` and:

```text
Unsupported variant: invalid
```

- [ ] **Step 4: Verify workflow files are present**

Run:

```powershell
Get-ChildItem .github\workflows | Select-Object Name
```

Expected:

```text
ci.yml
build-artifacts.yml
release.yml
```

- [ ] **Step 5: Optional local Docker smoke build for x86_64 standard package**

Run this only if Docker is available and the current machine can run Linux containers:

```powershell
bash scripts/ci-build-linux.sh standard x86_64
```

Expected:

```text
Created artifact: artifacts/TileMapService-v<version>-linux-x86_64.tar.gz
```

- [ ] **Step 6: Commit verification notes if documentation changed during verification**

If verification required documentation corrections, commit them:

```bash
git add README.md docs/BUILD_GUIDE.md
git commit -m "docs: refine release workflow notes"
```

If no files changed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - CI workflow: Task 1.
  - main/manual artifacts workflow: Task 5.
  - tag/manual release workflow: Task 6.
  - ARM64 standard package: Tasks 2, 3, 5, 6, 7, 8.
  - ARM64 staticx package: Tasks 2, 4, 5, 6, 7, 8.
  - Documentation: Tasks 7 and 8.
- Placeholder scan: no implementation placeholders are present in commands or code blocks.
- Type/name consistency:
  - Architecture names are `x86_64` and `aarch64`.
  - Docker platforms are `linux/amd64` and `linux/arm64`.
  - Artifact suffixes match the spec: `linux-aarch64` and `linux-staticx-aarch64`.
