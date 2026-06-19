# Windows 可移植版本构建脚本
# 使用 PyInstaller 构建 onedir 模式的打包目录

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TileMapService Windows 构建" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$archiveBaseName = "TileMapService-v$version-windows-x86_64"

# 检查 uv
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Host "❌ uv 未安装" -ForegroundColor Red
    Write-Host "请先安装 uv: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    Write-Host "或使用: pip install uv" -ForegroundColor Yellow
    exit 1
}

# 清理旧文件
Write-Host "[1] 清理旧文件..." -ForegroundColor Yellow
if (Test-Path "dist") {
    Remove-Item "dist" -Recurse -Force
}
if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}

# 确保依赖已安装
Write-Host ""
Write-Host "[2] 检查依赖..." -ForegroundColor Yellow
Write-Host "   同步项目依赖..." -ForegroundColor Gray
uv sync --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 依赖同步失败" -ForegroundColor Red
    exit 1
}

Write-Host "   同步构建工具..." -ForegroundColor Gray
uv sync --group build --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 构建工具安装失败" -ForegroundColor Red
    exit 1
}

# 运行 PyInstaller
Write-Host ""
Write-Host "[3] 打包应用（onedir 模式）..." -ForegroundColor Yellow
uv run pyinstaller tilemapservice.spec --clean

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 打包失败" -ForegroundColor Red
    exit 1
}

# 检查结果
Write-Host ""
if (Test-Path "dist/TileMapService") {
    $dirSize = (Get-ChildItem "dist/TileMapService" -Recurse | Measure-Object -Property Length -Sum).Sum
    $sizeMB = [math]::Round($dirSize / 1MB, 2)

    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✅ 打包成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 打包目录:" -ForegroundColor Cyan
    Write-Host "   路径: dist\TileMapService\" -ForegroundColor White
    Write-Host "   大小: $sizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 使用方法:" -ForegroundColor Yellow
    Write-Host "   cd dist\TileMapService" -ForegroundColor White
    Write-Host "   .\TileMapService.exe --port 8000" -ForegroundColor White
    Write-Host ""
    Write-Host "📋 兼容性:" -ForegroundColor Cyan
    Write-Host "   ✓ Windows 10+" -ForegroundColor Green
    Write-Host "   ✓ Windows Server 2016+" -ForegroundColor Green
    Write-Host ""

    # 创建发布包
    Write-Host "[4] 创建发布包..." -ForegroundColor Yellow

    # 显式复制 config.example.yaml 到应用目录
    Copy-Item "config\config.example.yaml" -Destination "dist\TileMapService\config.example.yaml" -Force
    Write-Host "   ✓ 已添加 config.example.yaml" -ForegroundColor Green

    # 压缩
    if (Get-Command tar -ErrorAction SilentlyContinue) {
        tar -czf "$archiveBaseName.tar.gz" -C dist TileMapService
        $tarFile = Get-Item "$archiveBaseName.tar.gz"
        Write-Host "   ✓ 已创建: $($tarFile.Name) ($([math]::Round($tarFile.Length/1MB, 2)) MB)" -ForegroundColor Green
    } elseif (Get-Command Compress-Archive -ErrorAction SilentlyContinue) {
        Compress-Archive -Path "dist\TileMapService" -DestinationPath "$archiveBaseName.zip" -Force
        $zipFile = Get-Item "$archiveBaseName.zip"
        Write-Host "   ✓ 已创建: $($zipFile.Name) ($([math]::Round($zipFile.Length/1MB, 2)) MB)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ 未找到压缩工具（tar 或 Compress-Archive）" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "✅ 完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 提示:" -ForegroundColor Yellow
    Write-Host "   首次运行时，请复制 config.example.yaml 为 config.yaml 并按需修改" -ForegroundColor White

} else {
    Write-Host "❌ 打包失败：未找到输出目录" -ForegroundColor Red
    exit 1
}
