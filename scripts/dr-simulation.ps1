# SADEN — ensaio de recuperacao de desastre (v1.2.2)
#
# Executa os cenarios de perda em ambiente ISOLADO (projeto compose proprio e
# diretorios tmp/dr-*). Nunca toca em data/ real nem em containers de producao.
#
# uso:  powershell -ExecutionPolicy Bypass -File scripts/dr-simulation.ps1
#
# Requer: Docker Desktop e a imagem saden:1.2.2 construida.

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$project = 'saden-dr'
$dataDir = Join-Path $root 'tmp/dr-data'
$offsiteDir = Join-Path $root 'tmp/dr-offsite'
$passphrase = 'dr-passphrase-para-teste-123'

$env:JWT_SECRET = 'dr-simulation-secret'
$env:SADEN_DATA_DIR = './tmp/dr-data'
$env:SADEN_OFFSITE_MODE = 'dir'
$env:SADEN_OFFSITE_DIR = '/app/offsite'
$env:SADEN_BACKUP_PASSPHRASE = $passphrase
$env:SADEN_BACKUP_INTERVAL_SECONDS = '3600'
$env:SADEN_OFFSITE_RETENTION = '5'
$env:COMPOSE_PROJECT_NAME = $project
$env:DR_OFFSITE_HOST = $offsiteDir

function Run-Docker {
  param([string[]]$Arguments)
  $out = & docker @Arguments 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) { throw ("docker " + ($Arguments -join ' ') + " falhou: " + $out.Trim()) }
  return $out
}
function Try-Docker {
  param([string[]]$Arguments)
  $out = & docker @Arguments 2>&1 | Out-String
  return $out
}

$results = New-Object System.Collections.ArrayList
function Record($name, $ok, $detail, $seconds) {
  [void]$results.Add([pscustomobject]@{ scenario = $name; ok = $ok; detail = $detail; seconds = [math]::Round($seconds, 1) })
  $tag = if ($ok) { 'OK  ' } else { 'FAIL' }
  Write-Host ("[{0}] {1} -> {2} ({3}s)" -f $tag, $name, $detail, [math]::Round($seconds, 1))
}
function Step($name, [scriptblock]$block) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $detail = & $block
    $sw.Stop()
    Record $name $true $detail $sw.Elapsed.TotalSeconds
  } catch {
    $sw.Stop()
    Record $name $false $_.Exception.Message $sw.Elapsed.TotalSeconds
    throw
  }
}
function Wait-Url($url, $timeout = 120) {
  $deadline = (Get-Date).AddSeconds($timeout)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3
      if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    Start-Sleep -Milliseconds 1500
  }
  throw "timeout aguardando $url"
}

Write-Host "`n=== SADEN DR simulation (projeto $project) ===" -ForegroundColor Cyan
Try-Docker @('compose', '-p', $project, 'down') | Out-Null
Try-Docker @('volume', 'rm', '-f', "${project}_saden-backups") | Out-Null
Remove-Item $dataDir, $offsiteDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $dataDir, $offsiteDir, (Join-Path $root 'tmp/mail-outbox') -Force | Out-Null

$composeFile = Join-Path $root 'tmp/dr-compose.override.yml'
$override = @"
services:
  saden-backup:
    volumes:
      - `${DR_OFFSITE_HOST}:/app/offsite
"@
[IO.File]::WriteAllText($composeFile, $override, (New-Object Text.UTF8Encoding($true)))

$composeArgs = @('compose', '-f', 'docker-compose.yml', '-f', $composeFile, '-p', $project)
function Compose { param([string[]]$Arguments) Run-Docker ($script:composeArgs + $Arguments) }

Step '0. subir ambiente e criar dados' {
  Compose @('up', '-d') | Out-Null
  Wait-Url 'http://127.0.0.1:3001/api/health' | Out-Null
  $reg = Invoke-RestMethod 'http://127.0.0.1:3001/api/auth/register' -Method Post -ContentType 'application/json' -Body (@{ name = 'DR'; email = 'dr@teste.local'; password = '123456' } | ConvertTo-Json)
  $null = Invoke-RestMethod 'http://127.0.0.1:3001/api/alerts' -Method Post -Headers @{ Authorization = "Bearer $($reg.token)" } -ContentType 'application/json' -Body (@{ series_id = 'yahoo:ZS=F:brl:sc60'; condition = 'price_above'; threshold = 0.01; label = 'dr' } | ConvertTo-Json)
  $script:token = $reg.token
  'servicos no ar, usuario e alerta criados'
}

Step '1. container web perdido' {
  Compose @('rm', '-sf', 'saden') | Out-Null
  Compose @('up', '-d', 'saden') | Out-Null
  Wait-Url 'http://127.0.0.1:3001/api/health' | Out-Null
  $alerts = Invoke-RestMethod 'http://127.0.0.1:3001/api/alerts' -Headers @{ Authorization = "Bearer $script:token" }
  "web recriado, $($alerts.alerts.Count) alerta(s) preservado(s)"
}

Step '2. worker perdido' {
  Compose @('rm', '-sf', 'saden-worker') | Out-Null
  Compose @('up', '-d', 'saden-worker') | Out-Null
  $deadline = (Get-Date).AddSeconds(120)
  $code = 0
  while ((Get-Date) -lt $deadline) {
    try { $r = Invoke-WebRequest 'http://127.0.0.1:3001/api/health/worker' -UseBasicParsing -TimeoutSec 3; $code = $r.StatusCode; if ($code -eq 200) { break } } catch { $code = $_.Exception.Response.StatusCode.value__ }
    Start-Sleep -Seconds 2
  }
  "worker recriado, health=$code"
}

Step '3. container de backup perdido' {
  Compose @('rm', '-sf', 'saden-backup') | Out-Null
  Compose @('up', '-d', 'saden-backup') | Out-Null
  $deadline = (Get-Date).AddSeconds(120); $ok = $false
  while ((Get-Date) -lt $deadline) {
    $logs = Try-Docker @('logs', "${project}-saden-backup-1")
    if ($logs -match 'backup_ok') { $ok = $true; break }
    Start-Sleep -Seconds 3
  }
  if (-not $ok) { throw 'backup nao produziu arquivo apos recriacao' }
  $count = (Run-Docker @('run', '--rm', '-v', "${project}_saden-backups:/b", 'saden:1.2.2', 'sh', '-c', 'ls /b/*.db | wc -l')).Trim()
  "backup recriado, arquivos no volume: $count"
}

Step '4. volume de backup perdido (recupera do off-site)' {
  Compose @('stop', 'saden-backup') | Out-Null
  Try-Docker @('volume', 'rm', '-f', "${project}_saden-backups") | Out-Null
  $remote = Get-ChildItem $offsiteDir -Filter '*.enc' | Sort-Object Name -Descending | Select-Object -First 1
  if (-not $remote) { throw 'nenhuma copia off-site encontrada' }
  $script = "const o=require('./src/backup/offsite');o.pull({key:'$($remote.Name)',outPath:'/out/dr-restored.db',cfg:o.config()}).then(r=>console.log('bytes '+r.bytes)).catch(e=>{console.error(e.message);process.exit(1)})"
  $out = Run-Docker @('run', '--rm', '-e', "SADEN_BACKUP_PASSPHRASE=$passphrase", '-e', 'SADEN_OFFSITE_MODE=dir', '-e', 'SADEN_OFFSITE_DIR=/offsite', '-w', '/app/backend', '-v', "${offsiteDir}:/offsite:ro", '-v', "${root}/tmp:/out", 'saden:1.2.2', 'node', '-e', $script)
  if (-not (Test-Path (Join-Path $root 'tmp/dr-restored.db'))) { throw 'arquivo restaurado nao foi criado' }
  "off-site $($remote.Name) recuperado e decifrado"
}

Step '5. ambiente completo perdido (reconstrucao)' {
  Compose @('down') | Out-Null
  Try-Docker @('volume', 'rm', '-f', "${project}_saden-backups") | Out-Null
  Remove-Item (Join-Path $dataDir '*') -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
  Run-Docker @('run', '--rm', '-w', '/app/backend', '-v', "${dataDir}:/app/data", '-v', "${root}/tmp:/src:ro", 'saden:1.2.2', 'sh', '-c', 'cp /src/dr-restored.db /app/data/saden.db') | Out-Null
  Compose @('up', '-d') | Out-Null
  Wait-Url 'http://127.0.0.1:3001/api/health' | Out-Null
  $login = Invoke-RestMethod 'http://127.0.0.1:3001/api/auth/login' -Method Post -ContentType 'application/json' -Body (@{ email = 'dr@teste.local'; password = '123456' } | ConvertTo-Json)
  $alerts = Invoke-RestMethod 'http://127.0.0.1:3001/api/alerts' -Headers @{ Authorization = "Bearer $($login.token)" }
  "ambiente reconstruido: login ok, $($alerts.alerts.Count) alerta(s)"
}

Step '6. backup corrompido e rejeitado' {
  $bad = Join-Path $root 'tmp/dr-bad'
  Remove-Item $bad -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $bad -Force | Out-Null
  [IO.File]::WriteAllText((Join-Path $bad 'saden-20260101-000000.db'), 'corrompido')
  $meta = '{"version":1,"file":"saden-20260101-000000.db","status":"ok","created_at":"2026-01-01T00:00:00.000Z","size":10,"sha256":"00"}'
  [IO.File]::WriteAllText((Join-Path $bad 'saden-20260101-000000.json'), $meta)
  $out = Try-Docker @('run', '--rm', '-w', '/app/backend', '-v', "${root}/tmp:/src:ro", 'saden:1.2.2', 'node', 'backend/scripts/restore-drill.js', '--out-dir', '/src/dr-bad')
  if ($out -match '"ok":true') { throw 'drill aceitou backup corrompido' }
  'drill rejeitou o backup corrompido'
}

Step '7. chave incorreta nao restaura' {
  $remote = Get-ChildItem $offsiteDir -Filter '*.enc' | Sort-Object Name -Descending | Select-Object -First 1
  $script = "const o=require('./src/backup/offsite');o.pull({key:'$($remote.Name)',outPath:'/out/dr-wrong-key.db',cfg:o.config()}).then(()=>console.log('RESTAUROU')).catch(e=>{console.log('ERRO '+e.message)})"
  $out = Try-Docker @('run', '--rm', '-e', 'SADEN_BACKUP_PASSPHRASE=chave-errada-mas-longa-999', '-e', 'SADEN_OFFSITE_MODE=dir', '-e', 'SADEN_OFFSITE_DIR=/offsite', '-w', '/app/backend', '-v', "${offsiteDir}:/offsite:ro", '-v', "${root}/tmp:/out", 'saden:1.2.2', 'node', '-e', $script)
  if ($out -match 'RESTAUROU') { throw 'restaurou com chave errada' }
  if (Test-Path (Join-Path $root 'tmp/dr-wrong-key.db')) { throw 'arquivo parcial criado com chave errada' }
  'chave errada rejeitada, nenhum arquivo gravado'
}

Step '8. destino indisponivel nao impede backup local' {
  # Renomear o diretorio no host NAO afeta um bind mount ja criado. A forma real
  # de simular destino inacessivel e remontar somente leitura e recriar o servico.
  Compose @('rm', '-sf', 'saden-backup') | Out-Null
  $roOverride = Join-Path $root 'tmp/dr-offsite-ro.yml'
  $ro = @"
services:
  saden-backup:
    volumes:
      - `${DR_OFFSITE_HOST}:/app/offsite:ro
"@
  [IO.File]::WriteAllText($roOverride, $ro, (New-Object Text.UTF8Encoding($true)))
  $roArgs = @('compose', '-f', 'docker-compose.yml', '-f', $roOverride, '-p', $project)
  Run-Docker ($roArgs + @('up', '-d', '--force-recreate', 'saden-backup')) | Out-Null

  $deadline = (Get-Date).AddSeconds(120); $line = $null
  while ((Get-Date) -lt $deadline) {
    $logs = Try-Docker @('logs', "${project}-saden-backup-1")
    $m = [regex]::Matches($logs, '\{"at".*?"event":"backup_ok".*\}')
    if ($m.Count -gt 0) { $line = $m[$m.Count - 1].Value; break }
    Start-Sleep -Seconds 3
  }
  if (-not $line) { throw 'backup local nao concluiu com destino inacessivel' }
  $parsed = $line | ConvertFrom-Json
  if ($parsed.offsite.status -ne 'error') { throw "off-site deveria falhar, veio '$($parsed.offsite.status)'" }
  "backup local ok ($($parsed.size) bytes), off-site=$($parsed.offsite.status) [$($parsed.offsite.reason)]"
}

Compose @('down') | Out-Null
Remove-Item (Join-Path $root 'tmp/dr-restored.db'), (Join-Path $root 'tmp/dr-wrong-key.db') -Force -ErrorAction SilentlyContinue

Write-Host "`n=== resumo ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize
$failed = @($results | Where-Object { -not $_.ok }).Count
$total = ($results | Measure-Object -Property seconds -Sum).Sum
Write-Host ("cenarios: {0} | falhas: {1} | tempo total: {2}s" -f $results.Count, $failed, [math]::Round($total, 0))
$results | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $root 'tmp/dr-results.json') -Encoding utf8
if ($failed -gt 0) { exit 1 }
