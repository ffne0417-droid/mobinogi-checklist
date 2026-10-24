[CmdletBinding()]
param([Parameter(Mandatory)][string]$AppRoot, [switch]$Apply)
$ErrorActionPreference='Stop'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source=Join-Path $repoRoot 'app'
$target=[IO.Path]::GetFullPath($AppRoot).TrimEnd('\','/')
if ($target -eq [IO.Path]::GetPathRoot($target).TrimEnd('\','/')) { throw 'A drive root is not an application directory.' }
if ($target.StartsWith($repoRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $repoRoot.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase) -or $target -eq $repoRoot) { throw 'Application and repository directories must not overlap.' }
foreach($relative in @('python/pythonw.exe','app/server.py','app/vendor/WebView2Loader.dll')) {
    if(-not(Test-Path -LiteralPath (Join-Path $target $relative) -PathType Leaf)){throw "Original distribution component missing: $relative"}
}
if(-not(Test-Path -LiteralPath (Join-Path $source 'connectorusage.py'))){throw 'Source snapshot is incomplete.'}
$python=Join-Path $target 'python/pythonw.exe'
if(@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" | Where-Object {$_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath) -eq $python}).Count){throw 'This installation has a running Python process. Close the app normally first.'}
$files=@(Get-ChildItem -LiteralPath $source -File -Recurse)
$backup=Join-Path ([IO.Path]::GetDirectoryName($target)) ('MobiWorks-source-backup-'+[DateTime]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,6))
Write-Output "Source files: $($files.Count); target: $target; backup on apply: $backup"
if(-not $Apply){Write-Output 'Plan only. No files changed. Pass -Apply after review.';return}
New-Item -ItemType Directory -Path $backup | Out-Null
$records=@()
foreach($file in $files){
    $relative=$file.FullName.Substring($source.Length+1)
    $dest=Join-Path (Join-Path $target 'app') $relative
    $existed=Test-Path -LiteralPath $dest -PathType Leaf
    if($existed){$old=Join-Path $backup $relative;New-Item -ItemType Directory -Path (Split-Path $old) -Force | Out-Null;Copy-Item -LiteralPath $dest -Destination $old}
    New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
    $records+=@{path=$relative;previouslyExisted=$existed}
}
[IO.File]::WriteAllText((Join-Path $backup 'changed-files.json'),($records | ConvertTo-Json -Depth 4),[Text.UTF8Encoding]::new($false))
Write-Output "Applied with backup: $backup. No app or queue was started. Original binaries and personal data were not copied or deleted."
