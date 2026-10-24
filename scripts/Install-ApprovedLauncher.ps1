[CmdletBinding()]
param([Parameter(Mandatory)][string]$AppRoot,[string]$TaskName='MobiWorks - Overlay Launch')
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(-not$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Open an administrator PowerShell with your one-time approval first. UAC is not disabled.'}
if($TaskName -notmatch '^MobiWorks - [A-Za-z0-9 -]{1,60}$'){throw 'Use a dedicated MobiWorks task name.'}
$app=[IO.Path]::GetFullPath($AppRoot)
$python=Join-Path $app 'python/pythonw.exe';$server=Join-Path $app 'app/server.py'
if(-not(Test-Path -LiteralPath $python -PathType Leaf) -or -not(Test-Path -LiteralPath $server -PathType Leaf)){throw 'Verified runtime and source paths are required.'}
if(Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue){throw 'An existing task was not overwritten. Inspect it and choose an unused dedicated name.'}
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$server+'"') -WorkingDirectory $app
$owner=New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $owner -Settings $settings -Description 'User-approved fixed MobiWorks app launcher; no UAC policy changes, arbitrary commands, queue start, or game confirmation input.' | Out-Null
Write-Output "Registered $TaskName. Not started. Protect application files from untrusted modification."
