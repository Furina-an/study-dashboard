# 构建 StudyDash 安卓 APK（release 签名版，可直接装到手机）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\build-apk.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build-apk.ps1 -Debug          # 出 debug 包，不签名
#   powershell -ExecutionPolicy Bypass -File scripts\build-apk.ps1 -SkipWeb        # 跳过 npm build，只重新打包
#   powershell -ExecutionPolicy Bypass -File scripts\build-apk.ps1 -ApiBase "http://192.168.1.10:8000"
param(
    [string]$ApiBase = "https://studydash-api.onrender.com",
    [switch]$Debug,
    [switch]$SkipWeb
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$AndroidDir = Join-Path $Frontend "android"
$Toolchain = Join-Path $Root "..\.toolchain"
$KeystorePath = Join-Path $AndroidDir "studydash-release.keystore"
$KeystoreProps = Join-Path $AndroidDir "keystore.properties"
$KeyAlias = "studydash"

# ---------- 1) 工具链 ----------
if (Test-Path (Join-Path $Toolchain "jdk-21")) {
    $env:JAVA_HOME = Join-Path $Toolchain "jdk-21"
    Write-Host "[i] 使用 JDK: $env:JAVA_HOME"
}
if (-not $env:JAVA_HOME) { throw "未设置 JAVA_HOME，请先安装 JDK 17/21（JDK 25 与当前 Gradle 不兼容）" }
if (Test-Path (Join-Path $Toolchain "android-sdk")) {
    $env:ANDROID_HOME = Join-Path $Toolchain "android-sdk"
    $env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
    Write-Host "[i] 使用 SDK: $env:ANDROID_HOME"
}
if (-not $env:ANDROID_HOME) { throw "未设置 ANDROID_HOME，请先安装 Android SDK（platform 35 + build-tools）" }

# ---------- 2) release 签名密钥（首次运行自动生成） ----------
function New-Keystore {
    $alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    $password = -join (1..28 | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
    $keytool = Join-Path $env:JAVA_HOME "bin\keytool.exe"
    & $keytool -genkeypair -v `
        -keystore $KeystorePath `
        -alias $KeyAlias `
        -keyalg RSA -keysize 2048 -validity 10000 `
        -storepass $password -keypass $password `
        -dname "CN=StudyDash, OU=Personal, O=StudyDash, L=Local, ST=Local, C=CN"
    if ($LASTEXITCODE -ne 0) { throw "keytool 生成密钥失败" }

    # 必须写成无 BOM 的 UTF-8，否则 Gradle 读到的第一个键会带 \ufeff 前缀
    $props = "storeFile=../studydash-release.keystore`nstorePassword=$password`nkeyAlias=$KeyAlias`nkeyPassword=$password`n"
    [System.IO.File]::WriteAllText($KeystoreProps, $props, (New-Object System.Text.UTF8Encoding($false)))

    Write-Host ""
    Write-Host "========== 已生成新的签名密钥（请务必自行备份！） =========="
    Write-Host "密钥文件 : $KeystorePath"
    Write-Host "配置     : $KeystoreProps"
    Write-Host "别名     : $KeyAlias"
    Write-Host "密码     : $password"
    Write-Host "说明     : 两个文件都已在 .gitignore 中，不会上传仓库；丢失后无法覆盖升级已安装的 App。"
    Write-Host "==========================================================="
    Write-Host ""
}

if (-not $Debug -and -not (Test-Path $KeystorePath)) {
    Write-Host "[i] 未找到 release 密钥，自动创建..."
    New-Keystore
}

# ---------- 3) 构建 Web ----------
Set-Location $Frontend
if (-not $SkipWeb) {
    Write-Host "==> 构建前端 (VITE_API_BASE=$ApiBase)"
    $env:VITE_API_BASE = $ApiBase
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
} else {
    Write-Host "[i] 已跳过前端构建（-SkipWeb）"
}

Write-Host "==> cap sync android"
npx.cmd cap sync android
if ($LASTEXITCODE -ne 0) { throw "cap sync 失败" }

# ---------- 4) Gradle 打包 ----------
Set-Location $AndroidDir
if ($Debug) {
    Write-Host "==> gradlew assembleDebug"
    & .\gradlew.bat assembleDebug
    $Apk = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"
} else {
    Write-Host "==> gradlew assembleRelease"
    & .\gradlew.bat assembleRelease
    $Apk = Join-Path $AndroidDir "app\build\outputs\apk\release\app-release.apk"
}
if ($LASTEXITCODE -ne 0) { throw "Gradle 构建失败，请检查 Android SDK（ANDROID_HOME 或 local.properties）" }
if (-not (Test-Path $Apk)) { throw "未找到产物：$Apk" }

# ---------- 5) 校验签名 ----------
if (-not $Debug) {
    $buildTools = Get-ChildItem (Join-Path $env:ANDROID_HOME "build-tools") -Directory |
        Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
    $apksigner = Join-Path $buildTools.FullName "apksigner.bat"
    if (Test-Path $apksigner) {
        Write-Host "==> 校验签名（$($buildTools.Name)）"
        & $apksigner verify --print-certs $Apk
    } else {
        Write-Host "[!] 未找到 apksigner，跳过签名校验"
    }
}

$size = (Get-Item $Apk).Length / 1MB
$hash = (Get-FileHash $Apk -Algorithm SHA256).Hash
Write-Host ""
Write-Host "========== 构建完成 =========="
Write-Host "APK  : $Apk"
Write-Host ("大小 : {0:N1} MB" -f $size)
Write-Host "SHA256: $hash"
Write-Host "接口 : $ApiBase"
Write-Host "安装 : 传到手机后用文件管理器点开即可（需允许「安装未知来源应用」）"
