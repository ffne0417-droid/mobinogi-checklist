$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifest=Get-Content -LiteralPath (Join-Path $repo 'MANIFEST.json') -Raw | ConvertFrom-Json
$bad=@();$count=0
foreach($entry in $manifest.files){
    if($entry.path -match '(^|/)(data-location\.json|lite\.json|queue\.json|settings\.json|queue_history\.json|connector_usage\.json|last-response\.json)$|\.(exe|dll|log|pyc|lnk)$|^runtime/|\.env$'){$bad+="Forbidden path: $($entry.path)";continue}
    $file=Join-Path $repo $entry.path
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){$bad+="Missing: $($entry.path)";continue}
    if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256){$bad+="Hash mismatch: $($entry.path)"}
    $text=[IO.File]::ReadAllText($file)
    if($text -match '(?i)ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|const TOKEN="[a-f0-9]{48}"|C:[/\\]Users[/\\]conan'){$bad+="Sensitive-pattern match (value withheld): $($entry.path)"}
    $count++
}
if($bad.Count){$bad;throw 'Snapshot check failed. Do not upload.'}
Write-Output "PASS $count manifest hashes and known secret/path exclusions. This heuristic scan is not a guarantee against all secrets."
