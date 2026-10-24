[CmdletBinding()]
param([Parameter(Mandatory)][string]$AppRoot,[Parameter(Mandatory)][string]$DataRoot,[switch]$Replace)
$ErrorActionPreference='Stop'
$app=[IO.Path]::GetFullPath($AppRoot)
if(-not(Test-Path -LiteralPath (Join-Path $app 'app/server.py') -PathType Leaf)){throw 'Application server was not found.'}
if(-not[IO.Path]::IsPathRooted($DataRoot) -or $DataRoot.StartsWith('\\')){throw 'DataRoot must be an absolute local path.'}
$data=[IO.Path]::GetFullPath($DataRoot).TrimEnd('\','/')
if($data -eq [IO.Path]::GetPathRoot($data).TrimEnd('\','/')){throw 'Do not use a drive root.'}
$dest=Join-Path $app 'app/data-location.json'
if(Test-Path -LiteralPath $dest){
    if(-not$Replace){throw 'Existing data location was not changed. Back it up and pass -Replace intentionally.'}
    Copy-Item -LiteralPath $dest -Destination ($dest+'.backup-'+[Guid]::NewGuid().ToString('N'))
}
New-Item -ItemType Directory -Path $data -Force | Out-Null
[IO.File]::WriteAllText($dest,(@{base=$data}|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
Write-Output 'Data location saved. No queue or settings were created or migrated. Restart the closed app intentionally.'
