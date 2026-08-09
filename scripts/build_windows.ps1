$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

& .\.venv\Scripts\python.exe scripts\generate_icons.py
$WebViewBootstrapper = "packaging\windows\MicrosoftEdgeWebview2Setup.exe"
if (-not (Test-Path $WebViewBootstrapper)) {
    Invoke-WebRequest `
        -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" `
        -OutFile $WebViewBootstrapper
}
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm interview_loom.spec
$AppVersion = & .\.venv\Scripts\python.exe -c "from app.metadata import APP_VERSION; print(APP_VERSION)"

$CertificatePath = Join-Path $env:TEMP "interview-loom-signing.pfx"
$SignTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1

function Sign-Artifact([string]$Path) {
    if ($env:WINDOWS_CERTIFICATE_BASE64 -and $env:WINDOWS_CERTIFICATE_PASSWORD -and $SignTool) {
        & $SignTool.FullName sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f $CertificatePath /p $env:WINDOWS_CERTIFICATE_PASSWORD $Path
    }
}

if ($env:WINDOWS_CERTIFICATE_BASE64) {
    [IO.File]::WriteAllBytes($CertificatePath, [Convert]::FromBase64String($env:WINDOWS_CERTIFICATE_BASE64))
    Sign-Artifact "dist\Interview Loom\Interview Loom.exe"
}

$InnoSetup = Get-Command iscc -ErrorAction SilentlyContinue
$DefaultInnoSetup = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if ($InnoSetup) {
    & $InnoSetup.Source "/DMyAppVersion=$AppVersion" packaging\windows\InterviewLoom.iss
} elseif (Test-Path $DefaultInnoSetup) {
    & $DefaultInnoSetup "/DMyAppVersion=$AppVersion" packaging\windows\InterviewLoom.iss
} else {
    Write-Host "Inno Setup не найден. Portable build: dist\Interview Loom"
}

$InstallerPath = "release\Interview-Loom-Setup-x64.exe"
if (-not (Test-Path $InstallerPath)) {
    throw "Inno Setup did not create $InstallerPath"
}
if (Test-Path $InstallerPath) {
    Sign-Artifact $InstallerPath
}
if (Test-Path $CertificatePath) {
    Remove-Item $CertificatePath -Force
}
