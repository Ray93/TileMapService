#!/bin/bash
# Linux 可移植版本构建脚本
# 使用 Docker 构建 onedir 模式的打包目录

set -e

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
ARCHIVE_NAME="TileMapService-v${VERSION}-linux-x86_64.tar.gz"

echo "========================================"
echo "  TileMapService Linux 构建"
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
rm -rf dist-linux
mkdir -p dist-linux

# 构建 Docker 镜像
echo ""
echo "[2] 构建 Docker 镜像（首次约 5 分钟）..."
docker build -t tilemapservice-linux-builder -f docker/Dockerfile.linux .

if [ $? -ne 0 ]; then
    echo "❌ Docker 镜像构建失败"
    exit 1
fi

# 运行打包
echo ""
echo "[3] 打包应用（onedir 模式）..."
docker run --rm -v "$(pwd)/dist-linux:/output" tilemapservice-linux-builder

# 检查结果
echo ""
if [ -d "dist-linux/TileMapService" ]; then
    SIZE=$(du -sh dist-linux/TileMapService | cut -f1)
    echo "========================================"
    echo "  ✅ 打包成功！"
    echo "========================================"
    echo ""
    echo "📦 打包目录:"
    echo "   路径: dist-linux/TileMapService/"
    echo "   大小: $SIZE"
    echo ""
    echo "🚀 使用方法:"
    echo "   cd TileMapService"
    echo "   chmod +x TileMapService"
    echo "   ./TileMapService --port 8000"
    echo ""
    echo "📋 兼容性 (Debian 11 基础):"
    echo "   ✓ Ubuntu 20.04+"
    echo "   ✓ Debian 11+"
    echo "   ✓ CentOS Stream 9+"
    echo "   ✓ Fedora 34+"
    echo ""

    # 创建发布包
    echo "[4] 创建发布包..."
    # config.example.yaml 已由 Docker 复制到 TileMapService 目录

    tar -czf "$ARCHIVE_NAME" -C dist-linux TileMapService
    TAR_SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
    echo "   ✓ 已创建: $ARCHIVE_NAME ($TAR_SIZE)"
    echo ""
    echo "✅ 完成！"
    echo ""
    echo "💡 CentOS 7 用户请使用 staticx 版本:"
    echo "   ./scripts/build-linux-staticx.sh"
else
    echo "❌ 打包失败"
    exit 1
fi
