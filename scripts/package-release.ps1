$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VersionFile = Join-Path $RootDir "VERSION"
$ReleaseDir = Join-Path $RootDir "releases"

if (-not (Test-Path $VersionFile)) {
    throw "VERSION 文件不存在。"
}

$Version = (Get-Content $VersionFile -Raw).Trim()
$PackageName = "slz-devops-$Version"
$PackagePath = Join-Path $ReleaseDir "$PackageName.zip"
$StageDir = Join-Path ([System.IO.Path]::GetTempPath()) ("$PackageName-" + [System.Guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path $PackagePath) {
    Remove-Item $PackagePath -Force
}

New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

$ExcludeNames = @(".git", "data", "releases", ".env")

Get-ChildItem -Force $RootDir | Where-Object {
    $ExcludeNames -notcontains $_.Name
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $StageDir -Recurse -Force
}

Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $PackagePath -CompressionLevel Optimal
Remove-Item $StageDir -Recurse -Force

Write-Host "发行包已生成: $PackagePath"
