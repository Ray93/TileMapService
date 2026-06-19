# Linux 可移植版本构建脚本 (Windows)
# 使用 Docker 构建 onedir 模式的打包目录

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TileMapService Linux 构建" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$archiveName = "TileMapService-v$version-linux-x86_64.tar.gz"

# 检查 Docker
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "❌ Docker 未安装" -ForegroundColor Red
    Write-Host "请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# 清理旧文件
Write-Host "[1] 清理旧文件..." -ForegroundColor Yellow
if (Test-Path "dist-linux") {
    Remove-Item "dist-linux" -Recurse -Force
}
New-Item -ItemType Directory -Path "dist-linux" | Out-Null

# 构建 Docker 镜像
Write-Host ""
Write-Host "[2] 构建 Docker 镜像（首次约 5 分钟）..." -ForegroundColor Yellow
docker build -t tilemapservice-linux-builder -f docker/Dockerfile.linux .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker 镜像构建失败" -ForegroundColor Red
    exit 1
}

# 运行打包
Write-Host ""
Write-Host "[3] 打包应用（onedir 模式）..." -ForegroundColor Yellow
docker run --rm -v "${PWD}/dist-linux:/output" tilemapservice-linux-builder

# 检查结果
Write-Host ""
if (Test-Path "dist-linux/TileMapService") {
    $dirSize = (Get-ChildItem "dist-linux/TileMapService" -Recurse | Measure-Object -Property Length -Sum).Sum
    $sizeMB = [math]::Round($dirSize / 1MB, 2)

    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✅ 打包成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 打包目录:" -ForegroundColor Cyan
    Write-Host "   路径: dist-linux/TileMapService/" -ForegroundColor White
    Write-Host "   大小: $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 使用方法 (在 Linux 上):" -ForegroundColor Yellow
    Write-Host "   cd TileMapService" -ForegroundColor White
    Write-Host "   chmod +x TileMapService" -ForegroundColor White
    Write-Host "   ./TileMapService --port 8000" -ForegroundColor White
    Write-Host ""
    Write-Host "📋 兼容性 (Debian 11 基础):" -ForegroundColor Cyan
    Write-Host "   ✓ Ubuntu 20.04+" -ForegroundColor Green
    Write-Host "   ✓ Debian 11+" -ForegroundColor Green
    Write-Host "   ✓ CentOS Stream 9+" -ForegroundColor Green
    Write-Host "   ✓ Fedora 34+" -ForegroundColor Green
    Write-Host ""

    # 创建发布包
    Write-Host "[4] 创建发布包..." -ForegroundColor Yellow
    # config.example.yaml 已由 Docker 复制到 TileMapService 目录

    # 检查 tar.gz 是否已由 Docker 创建
    if (Test-Path "dist-linux/$archiveName") {
        Move-Item "dist-linux/$archiveName" -Destination "." -Force
        $tarFile = Get-Item $archiveName
        Write-Host "   ✓ 已创建: $($tarFile.Name) ($([math]::Round($tarFile.Length/1MB, 2)) MB)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ 未找到 tar.gz 文件（Docker 内部打包可能失败）" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "✅ 完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 CentOS 7 用户请使用 staticx 版本:" -ForegroundColor Yellow
    Write-Host "   .\scripts\build-linux-staticx.ps1" -ForegroundColor White

} else {
    Write-Host "❌ 打包失败" -ForegroundColor Red
    exit 1
}
