# Linux StaticX 版本构建脚本 (Windows)
# 使用 Docker + PyInstaller (onefile) + staticx 构建静态链接可执行文件

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TileMapService Linux StaticX 构建" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$archiveName = "TileMapService-v$version-linux-staticx-x86_64.tar.gz"

# 检查 Docker
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "❌ Docker 未安装" -ForegroundColor Red
    Write-Host "请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# 清理旧文件
Write-Host "[1] 清理旧文件..." -ForegroundColor Yellow
if (Test-Path "dist-static") {
    Remove-Item "dist-static" -Recurse -Force
}
New-Item -ItemType Directory -Path "dist-static" | Out-Null

# 构建 Docker 镜像
Write-Host ""
Write-Host "[2] 构建 Docker 镜像（首次约 5-8 分钟）..." -ForegroundColor Yellow
docker build -t tilemapservice-static -f docker/Dockerfile.staticx .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker 镜像构建失败" -ForegroundColor Red
    exit 1
}

# 运行打包
Write-Host ""
Write-Host "[3] 打包应用（staticx 静态链接）..." -ForegroundColor Yellow
docker run --rm -v "${PWD}/dist-static:/output" tilemapservice-static

# 检查结果
Write-Host ""
if (Test-Path "dist-static/TileMapService") {
    $dirSize = (Get-ChildItem "dist-static/TileMapService" -Recurse | Measure-Object -Property Length -Sum).Sum
    $sizeMB = [math]::Round($dirSize / 1MB, 2)

    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✅ StaticX 打包成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 打包目录:" -ForegroundColor Cyan
    Write-Host "   路径: dist-static/TileMapService/" -ForegroundColor White
    Write-Host "   大小: $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 使用方法 (在 Linux 上):" -ForegroundColor Yellow
    Write-Host "   cd TileMapService" -ForegroundColor White
    Write-Host "   chmod +x TileMapService" -ForegroundColor White
    Write-Host "   ./TileMapService --port 8000" -ForegroundColor White
    Write-Host ""
    Write-Host "📋 兼容性 (StaticX 静态链接):" -ForegroundColor Cyan
    Write-Host "   ✓ CentOS 7.0+" -ForegroundColor Green
    Write-Host "   ✓ RHEL 7.0+" -ForegroundColor Green
    Write-Host "   ✓ Ubuntu 16.04+" -ForegroundColor Green
    Write-Host "   ✓ Debian 8+" -ForegroundColor Green
    Write-Host "   ✓ 任何 glibc 2.17+ 的 Linux 发行版" -ForegroundColor Green
    Write-Host ""

    # 创建发布包
    Write-Host "[4] 创建发布包..." -ForegroundColor Yellow
    # config.example.yaml 已由 Docker 复制到 TileMapService 目录

    # 检查 tar.gz 是否已由 Docker 创建
    if (Test-Path "dist-static/$archiveName") {
        Move-Item "dist-static/$archiveName" -Destination "." -Force
        $tarFile = Get-Item $archiveName
        Write-Host "   ✓ 已创建: $($tarFile.Name) ($([math]::Round($tarFile.Length/1MB, 2)) MB)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ 未找到 tar.gz 文件（Docker 内部打包可能失败）" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "✅ 完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 提示:" -ForegroundColor Yellow
    Write-Host "   StaticX 静态链接版 - 单文件可执行 + 外置静态文件" -ForegroundColor White
    Write-Host "   所有依赖静态链接，无需系统库" -ForegroundColor White
    Write-Host "   兼容旧版 Linux 系统（CentOS 7.0+, glibc 2.17+）" -ForegroundColor White
    Write-Host "   包含 PROJ 数据库以支持坐标转换" -ForegroundColor White

} else {
    Write-Host "❌ 打包失败" -ForegroundColor Red
    exit 1
}
