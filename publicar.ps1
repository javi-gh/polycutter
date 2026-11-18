# Publica este proyecto en GitHub (no requiere saber git).
# Uso: doble clic en publicar.cmd  (o: powershell -ExecutionPolicy Bypass -File publicar.ps1)

param(
    [string]$Repo = "PolyCutter",
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Tool($name, $fallback) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    if (Test-Path $fallback) { return $fallback }
    throw "No se encontro $name. Reinstala con winget: winget install $name"
}

$git = Find-Tool "git" "C:\Program Files\Git\cmd\git.exe"
$gh = Find-Tool "gh" "C:\Program Files\GitHub CLI\gh.exe"

Write-Host "== PolyCutter: publicacion en GitHub ==" -ForegroundColor Cyan

# 1) Login en GitHub si hace falta
& $gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Iniciando sesion en GitHub (sigue las instrucciones)..." -ForegroundColor Yellow
    & $gh auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) { throw "Login de GitHub cancelado o fallido" }
}

$login = (& $gh api user -q .login).Trim()
Write-Host "Sesion: $login" -ForegroundColor Green

# 2) Identidad local de git (solo este repositorio)
& $git config user.name $login
& $git config user.email "$login@users.noreply.github.com"

# 3) Repositorio local y commit
if (-not (Test-Path ".git")) { & $git init -b main | Out-Null }
& $git add -A
& $git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    & $git commit -m "PolyCutter 1.0.0" | Out-Null
    Write-Host "Commit creado." -ForegroundColor Green
} else {
    Write-Host "Sin cambios pendientes de commit." -ForegroundColor DarkGray
}

# 4) Repositorio remoto
$desc = "Addon de Blender para separar extremidades con un lazo editable"
$exists = $true
& $gh repo view "$login/$Repo" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { $exists = $false }

if (-not $exists) {
    & $gh repo create $Repo "--$Visibility" --source . --remote origin `
        --description $desc --disable-wiki
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el repositorio $Repo" }
    Write-Host "Repositorio creado: https://github.com/$login/$Repo" -ForegroundColor Green
} else {
    $remote = (& $git remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0) {
        & $git remote add origin "https://github.com/$login/$Repo.git"
    }
    Write-Host "Repositorio existente: https://github.com/$login/$Repo" -ForegroundColor Yellow
}

# 5) Subir rama y version
& $git push -u origin main
if ($LASTEXITCODE -ne 0) { throw "No se pudo subir la rama main" }

& $gh repo edit "$login/$Repo" --add-topic blender,blender-addon,mesh,cutter,boolean | Out-Null

$tagExists = (& $git tag -l "v1.0.0")
if (-not $tagExists) {
    & $git tag "v1.0.0"
    & $git push origin "v1.0.0"
}

Write-Host ""
Write-Host "Listo: https://github.com/$login/$Repo" -ForegroundColor Cyan
Write-Host "La release v1.0.0 se genera sola en Actions (pestana Actions/Releases)."
