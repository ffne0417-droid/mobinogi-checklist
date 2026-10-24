[CmdletBinding()]
param([Parameter(Mandatory)][string]$AppRoot)
$ErrorActionPreference='Stop'
$app=[IO.Path]::GetFullPath($AppRoot)
$python=Join-Path $app 'python/pythonw.exe';$server=Join-Path $app 'app/server.py'
if(-not(Test-Path -LiteralPath $python -PathType Leaf) -or -not(Test-Path -LiteralPath $server -PathType Leaf)){throw 'Original runtime and applied sources are required.'}
Start-Process -FilePath $python -ArgumentList ('"'+$server+'"') -WorkingDirectory $app -WindowStyle Hidden
Write-Output 'App launch requested. This is not queue/start or a successful game command.'
