#!/bin/bash
# Linux StaticX 版本构建脚本
# 使用 Docker + PyInstaller (onefile) + staticx 构建静态链接可执行文件

set -e

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
ARCHIVE_NAME="TileMapService-v${VERSION}-linux-staticx-x86_64.tar.gz"

echo "========================================"
echo "  TileMapService Linux StaticX 构建"
echo "========================================"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 清理旧文件
echo "[1] 清理旧文件..."
rm -rf dist-static
mkdir -p dist-static

# 构建 Docker 镜像
echo ""
echo "[2] 构建 Docker 镜像（首次约 5-8 分钟）..."
docker build -t tilemapservice-static -f docker/Dockerfile.staticx .

if [ $? -ne 0 ]; then
    echo "❌ Docker 镜像构建失败"
    exit 1
fi

# 运行打包
echo ""
echo "[3] 打包应用（staticx 静态链接）..."
docker run --rm -v "$(pwd)/dist-static:/output" tilemapservice-static

# 检查结果
echo ""
if [ -d "dist-static/TileMapService" ]; then
    SIZE=$(du -sh dist-static/TileMapService | cut -f1)
    echo "========================================"
    echo "  ✅ StaticX 打包成功！"
    echo "========================================"
    echo ""
    echo "📦 打包目录:"
    echo "   路径: dist-static/TileMapService/"
    echo "   大小: $SIZE"
    echo ""
    echo "🚀 使用方法:"
    echo "   cd TileMapService"
    echo "   chmod +x TileMapService"
    echo "   ./TileMapService --port 8000"
    echo ""
    echo "📋 兼容性 (StaticX 静态链接):"
    echo "   ✓ CentOS 7.0+"
    echo "   ✓ RHEL 7.0+"
    echo "   ✓ Ubuntu 16.04+"
    echo "   ✓ Debian 8+"
    echo "   ✓ 任何 glibc 2.17+ 的 Linux 发行版"
    echo ""

    # 创建发布包
    echo "[4] 创建发布包..."
    # config.example.yaml 已由 Docker 复制到 TileMapService 目录

    # 检查 tar.gz 是否已由 Docker 创建
    if [ -f "dist-static/$ARCHIVE_NAME" ]; then
        mv "dist-static/$ARCHIVE_NAME" .
        TAR_SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
        echo "   ✓ 已创建: $ARCHIVE_NAME ($TAR_SIZE)"
    else
        echo "   ⚠ 未找到 tar.gz 文件（Docker 内部打包可能失败）"
    fi

    echo ""
    echo "✅ 完成！"
    echo ""
    echo "💡 提示:"
    echo "   StaticX 静态链接版 - 单文件可执行 + 外置静态文件"
    echo "   所有依赖静态链接，无需系统库"
    echo "   兼容旧版 Linux 系统（CentOS 7.0+, glibc 2.17+）"
    echo "   包含 PROJ 数据库以支持坐标转换"
else
    echo "❌ 打包失败"
    exit 1
fi
