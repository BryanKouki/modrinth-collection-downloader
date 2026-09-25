#Requires -Version 5.0
<#
.SYNOPSIS
    Modrinth Collection Downloader - native Windows edition (PowerShell)

.DESCRIPTION
    A single PowerShell script, no Python involved at all. Uses only what
    already ships with Windows 10/11 (Windows PowerShell 5.1): Invoke-RestMethod
    and Invoke-WebRequest to talk to the Modrinth API and download files, and
    Compress-Archive to build the .zip. Nothing to install.

.PARAMETER Collection
    Collection ID or URL.
.PARAMETER McVersion
    Minecraft version (e.g. 1.21.1).
.PARAMETER Loader
    Mod loader (e.g. fabric, forge, neoforge, paper).
.PARAMETER Dest
    Destination folder (default: current directory).
.PARAMETER Zip
    Save as a single .zip instead of a folder.
.PARAMETER NoMods
    Exclude mods, plugins and datapacks.
.PARAMETER NoResourcepacks
    Exclude resource/texture packs.
.PARAMETER NoShaders
    Exclude shaders.
.PARAMETER NoDeps
    Do not download required dependencies.
.PARAMETER AllowBeta
    Do not prefer stable releases; use the newest version available even if alpha/beta.
.PARAMETER Exclude
    Comma-separated project IDs/slugs to exclude from the download.
.PARAMETER ListItems
    Print every item in the collection, with its ID, and exit without downloading.
.PARAMETER Lang
    Output language: en or pt (default: en).
.PARAMETER Yes
    Skip the confirmation prompt.

.EXAMPLE
    .\modrinth_dl.ps1
    Fully interactive: asks for anything not passed as a parameter.

.EXAMPLE
    .\modrinth_dl.ps1 -Collection N6yU1DBr -McVersion 1.21.1 -Loader fabric -Dest .\output -Zip -Yes

.EXAMPLE
    .\modrinth_dl.ps1 -Collection N6yU1DBr -ListItems

.NOTES
    Safety: this script only queries Modrinth's public API (api.modrinth.com)
    and downloads official files hosted by Modrinth itself (cdn.modrinth.com).
    It does not collect, send, or execute anything beyond that.
#>

param(
    [string]$Collection,
    [string]$McVersion,
    [string]$Loader,
    [string]$Dest,
    [switch]$Zip,
    [switch]$Mrpack,
    [switch]$NoMods,
    [switch]$NoResourcepacks,
    [switch]$NoShaders,
    [switch]$NoDeps,
    [switch]$AllowBeta,
    [string]$Exclude,
    [switch]$ListItems,
    [string]$Lang = "en",
    [switch]$Yes,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {
    # Older PowerShell/.NET without Tls12 in the enum; safe to ignore and
    # let the system default apply.
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

$ApiBase = "https://api.modrinth.com"
$AppVersion = "1.0.0"
$Author = "BryanKouki"
$UserAgent = "$Author/ModrinthCollectionDownloaderPS/$AppVersion (github.com/$Author)"

$PluginLoaders = @("bukkit", "spigot", "paper", "purpur", "folia", "sponge", "velocity", "waterfall", "bungeecord")
$DatapackLoaders = @("datapack")

$script:LangCode = if ($Lang -eq "pt") { "pt" } else { "en" }

# ---------------------------------------------------------------------------
# Messages (English / Portuguese)
# ---------------------------------------------------------------------------

$Messages = @{
    en = @{
        prompt_collection            = "Collection ID or URL: "
        prompt_version                = "Minecraft version (e.g. 1.21.1): "
        prompt_loader                  = "Mod loader (e.g. fabric, forge, neoforge, paper): "
        prompt_dest                     = "Destination folder [.]: "
        prompt_confirm                   = "Proceed with the download? [Y/n]: "
        err_no_collection                 = "No collection ID or URL was given."
        err_collection_not_found           = "Collection not found or inaccessible."
        err_empty_collection                = "The collection has no items."
        err_no_version                       = "No Minecraft version was given."
        err_no_loader                         = "No mod loader was given."
        err_no_category                        = "At least one category must be left enabled."
        err_mrpack_unsupported_loader           = ".mrpack only supports the fabric, forge, neoforge or quilt loaders. Pick one of those, or choose a different save format."
        info_fetching_collection                = "Fetching collection information..."
        info_fetching_items                      = "Fetching item details..."
        info_aborted                              = "Aborted."
        items_header                               = "Items in this collection:"
        log_start                                   = "Starting download..."
        log_zipping                                  = "Zipping files..."
        log_resolving_loader_version                  = "Resolving the latest loader version..."
        log_loader_version_unknown                      = "Could not automatically determine the loader version - you may need to set it manually after importing the pack."
        log_building_mrpack                              = "Building the .mrpack file..."
        log_mrpack_file_added                             = "added to the modpack index."
        log_mrpack_unsupported_category                    = "files aren't supported in .mrpack (only mods, resource packs and shaders are)."
        log_moving                                    = "Moving files to the destination..."
        log_done                                       = "Download finished."
        reason_project_not_found                        = "could not fetch the project's details"
        reason_no_file                                   = "no downloadable file was found"
        reason_download_error                             = "the download failed"
        reason_no_version                                  = "no version published for that Minecraft version/loader"
        summary_header                                      = "===== SUMMARY ====="
        summary_output                                       = "Saved to:"
        summary_failed_header                                 = "Failed items:"
        summary_incompatible_header                            = "Incompatible items:"
    }
    pt = @{
        prompt_collection            = "ID ou URL da colecao: "
        prompt_version                = "Versao do Minecraft (ex: 1.21.1): "
        prompt_loader                  = "Mod loader (ex: fabric, forge, neoforge, paper): "
        prompt_dest                     = "Pasta de destino [.]: "
        prompt_confirm                   = "Continuar com o download? [S/n]: "
        err_no_collection                 = "Nenhum ID ou URL de colecao foi informado."
        err_collection_not_found           = "Colecao nao encontrada ou inacessivel."
        err_empty_collection                = "A colecao nao tem itens."
        err_no_version                       = "Nenhuma versao do Minecraft foi informada."
        err_no_loader                         = "Nenhum mod loader foi informado."
        err_no_category                        = "Pelo menos uma categoria precisa ficar habilitada."
        err_mrpack_unsupported_loader           = ".mrpack so e compativel com os loaders fabric, forge, neoforge ou quilt. Escolha um deles, ou selecione outro formato pra salvar."
        info_fetching_collection                = "Buscando informacoes da colecao..."
        info_fetching_items                      = "Buscando detalhes dos itens..."
        info_aborted                              = "Cancelado."
        items_header                               = "Itens desta colecao:"
        log_start                                   = "Iniciando download..."
        log_zipping                                  = "Compactando arquivos..."
        log_resolving_loader_version                  = "Resolvendo a versao mais recente do loader..."
        log_loader_version_unknown                      = "Nao foi possivel determinar automaticamente a versao do loader - talvez seja necessario ajustar manualmente depois de importar o pacote."
        log_building_mrpack                              = "Montando o arquivo .mrpack..."
        log_mrpack_file_added                             = "adicionado ao indice do modpack."
        log_mrpack_unsupported_category                    = "nao sao suportados em .mrpack (so mods, resource packs e shaders sao)."
        log_moving                                    = "Movendo arquivos para o destino..."
        log_done                                       = "Download finalizado."
        reason_project_not_found                        = "nao foi possivel obter os dados do projeto"
        reason_no_file                                   = "nenhum arquivo para download foi encontrado"
        reason_download_error                             = "o download falhou"
        reason_no_version                                  = "nenhuma versao publicada para essa versao/loader"
        summary_header                                      = "===== RESUMO ====="
        summary_output                                       = "Salvo em:"
        summary_failed_header                                 = "Itens que falharam:"
        summary_incompatible_header                            = "Itens incompativeis:"
    }
}

function T {
    param([string]$Key)
    $table = $Messages[$script:LangCode]
    if ($table.ContainsKey($Key)) { return $table[$Key] }
    return $Key
}

function Show-Help {
    Write-Host @"
Modrinth Collection Downloader - native Windows edition (PowerShell)

Usage: modrinth_dl.ps1 [options]
   or: modrinth_dl.bat [options]   (thin launcher, same options)

  -Collection ID_OR_URL     Collection ID or URL
  -McVersion VERSION        Minecraft version (e.g. 1.21.1)
  -Loader LOADER            Mod loader (e.g. fabric, forge, neoforge, paper)
  -Dest PATH                Destination folder (default: current directory)
  -Zip                      Save as a single .zip instead of a folder
  -Mrpack                   Save as a .mrpack (Modrinth Modpack) instead of a folder -
                            just download references for a launcher like Prism/MultiMC,
                            no actual files. Only works with fabric/forge/neoforge/quilt;
                            plugins and datapacks are left out.
  -NoMods                   Exclude mods, plugins and datapacks
  -NoResourcepacks          Exclude resource/texture packs
  -NoShaders                Exclude shaders
  -NoDeps                   Do not download required dependencies
  -AllowBeta                Do not prefer stable releases
  -Exclude ID1,ID2,...      Comma-separated project IDs/slugs to exclude
  -ListItems                Print the collection's items and exit
  -Lang en|pt               Output language (default: en)
  -Yes                      Skip the confirmation prompt
  -Help                     Show this help and exit

Examples:
  .\modrinth_dl.ps1
  .\modrinth_dl.ps1 -Collection N6yU1DBr -McVersion 1.21.1 -Loader fabric -Dest .\out -Zip -Yes
  .\modrinth_dl.ps1 -Collection N6yU1DBr -ListItems
"@
}

if ($Help) {
    Show-Help
    exit 0
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

function Api-Get {
    param([string]$Path)
    try {
        $headers = @{ "User-Agent" = $UserAgent; "Accept" = "application/json" }
        return Invoke-RestMethod -Uri "$ApiBase$Path" -Headers $headers -TimeoutSec 20 -ErrorAction Stop
    } catch {
        return $null
    }
}

function Download-File {
    param([string]$Url, [string]$Destination)
    $tmp = "$Destination.part"
    $dir = Split-Path -Parent $Destination
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    try {
        $headers = @{ "User-Agent" = $UserAgent }
        Invoke-WebRequest -Uri $Url -Headers $headers -OutFile $tmp -TimeoutSec 60 -ErrorAction Stop | Out-Null
        if ((Test-Path -LiteralPath $tmp) -and ((Get-Item -LiteralPath $tmp).Length -gt 0)) {
            Move-Item -LiteralPath $tmp -Destination $Destination -Force
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    }
}

function Get-CollectionId {
    param([string]$RawInput)
    if ($RawInput -match 'modrinth\.com/collection/([^/?#]+)') {
        return $Matches[1]
    }
    return $RawInput.Trim()
}

function Get-SafeFilename {
    param([string]$Name)
    $clean = [regex]::Replace($Name, '[<>:"/\\|?*]', "_")
    $clean = $clean.TrimEnd()
    if ([string]::IsNullOrWhiteSpace($clean)) { return "modrinth-collection" }
    return $clean
}

function Get-UniquePath {
    param([string]$BasePath, [string]$Suffix)
    $candidate = $BasePath
    $i = 2
    while (Test-Path -LiteralPath "$candidate$Suffix") {
        $candidate = "$BasePath ($i)"
        $i++
    }
    return $candidate
}

# ---------------------------------------------------------------------------
# Categorization / version selection
# ---------------------------------------------------------------------------

function Get-Category {
    param([string]$ProjectType, [string[]]$Loaders)
    $loadersLower = @($Loaders | ForEach-Object { $_.ToLower() })
    if ($ProjectType -eq "shader") { return "shaderpacks" }
    if ($ProjectType -eq "resourcepack") { return "resourcepacks" }
    if ((@($loadersLower | Where-Object { $DatapackLoaders -contains $_ })).Count -gt 0) { return "datapacks" }
    if ((@($loadersLower | Where-Object { $PluginLoaders -contains $_ })).Count -gt 0) { return "plugins" }
    return "mods"
}

function Select-Version {
    param($Versions, [string]$TargetMcVersion, [string]$TargetLoader, [string]$ProjectType, [bool]$PreferStable)

    $loaderLower = $TargetLoader.ToLower()
    $sameVersion = @($Versions | Where-Object { $_.game_versions -and ($_.game_versions -contains $TargetMcVersion) })

    $candidates = @()
    if ($ProjectType -eq "resourcepack") {
        $candidates = @($sameVersion | Where-Object {
            $ld = @($_.loaders)
            ($ld.Count -eq 0) -or ((@($ld | ForEach-Object { $_.ToLower() })) -contains "minecraft")
        })
    } elseif ($ProjectType -eq "shader") {
        $candidates = $sameVersion
    } else {
        $exact = @($sameVersion | Where-Object {
            (@($_.loaders | ForEach-Object { $_.ToLower() })) -contains $loaderLower
        })
        if ($exact.Count -gt 0) {
            $candidates = $exact
        } else {
            $special = $PluginLoaders + $DatapackLoaders
            $candidates = @($sameVersion | Where-Object {
                $ld = @($_.loaders | ForEach-Object { $_.ToLower() })
                (@($ld | Where-Object { $special -contains $_ })).Count -gt 0
            })
        }
    }

    if ($candidates.Count -eq 0) { return $null }

    $sorted = @($candidates | Sort-Object -Property date_published -Descending)

    if ($PreferStable) {
        $releases = @($sorted | Where-Object { $_.version_type -eq "release" })
        if ($releases.Count -gt 0) { return $releases[0] }
    }
    return $sorted[0]
}

# ---------------------------------------------------------------------------
# .mrpack (Modrinth Modpack) export
# ---------------------------------------------------------------------------
# A .mrpack only needs each file's official download URL and hash - both
# already included in the version data the Modrinth API returns - so
# building one requires no extra file downloads at all. Resolving a
# concrete loader *version*, though, needs each loader's own official
# metadata API (the Modrinth API only knows the loader's name):
#
#   Fabric   -> meta.fabricmc.net      Forge    -> files.minecraftforge.net
#   Quilt    -> meta.quiltmc.org       NeoForge -> maven.neoforged.net
#
# These are only ever contacted when -Mrpack is used.

$MrpackDependencyKey = @{
    fabric = "fabric-loader"
    quilt = "quilt-loader"
    forge = "forge"
    neoforge = "neoforge"
}
$MrpackSupportedFolders = @("mods", "resourcepacks", "shaderpacks")

function Test-MrpackLoaderSupported {
    param([string]$LoaderName)
    return $MrpackDependencyKey.ContainsKey($LoaderName.ToLower())
}

function Get-LatestLoaderVersion {
    param([string]$LoaderName, [string]$TargetMcVersion)
    $loaderLower = $LoaderName.ToLower()
    try {
        if ($loaderLower -eq "fabric") {
            $versions = Invoke-RestMethod -Uri "https://meta.fabricmc.net/v2/versions/loader" -TimeoutSec 15 -ErrorAction Stop
            $stable = @($versions | Where-Object { $_.loader.stable })
            $pick = if ($stable.Count -gt 0) { $stable[0] } elseif (@($versions).Count -gt 0) { $versions[0] } else { $null }
            if ($pick) { return $pick.loader.version }
            return $null
        }
        if ($loaderLower -eq "quilt") {
            $versions = @(Invoke-RestMethod -Uri "https://meta.quiltmc.org/v3/versions/loader" -TimeoutSec 15 -ErrorAction Stop)
            if ($versions.Count -gt 0) { return $versions[0].version }
            return $null
        }
        if ($loaderLower -eq "forge") {
            $data = Invoke-RestMethod -Uri "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json" -TimeoutSec 15 -ErrorAction Stop
            $recKey = "$TargetMcVersion-recommended"
            $latKey = "$TargetMcVersion-latest"
            $value = $data.promos.$recKey
            if (-not $value) { $value = $data.promos.$latKey }
            return $value
        }
        if ($loaderLower -eq "neoforge") {
            $data = Invoke-RestMethod -Uri "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge" -TimeoutSec 15 -ErrorAction Stop
            $versions = @($data.versions)
            $parts = $TargetMcVersion -split '\.'
            if ($parts.Count -ge 2) {
                $minor = $parts[1]
                $patch = if ($parts.Count -gt 2) { $parts[2] } else { "0" }
                $prefix = "$minor.$patch."
                $matching = @($versions | Where-Object { $_.StartsWith($prefix) })
                if ($matching.Count -gt 0) { return $matching[-1] }
            }
            if ($versions.Count -gt 0) { return $versions[-1] }
            return $null
        }
    } catch {
        return $null
    }
    return $null
}

function New-MrpackFileEntry {
    param([string]$Folder, [string]$Filename, [string]$Url, $Size, $Hashes, [string]$ClientSide, [string]$ServerSide)
    $hashObj = [ordered]@{}
    if ($Hashes) {
        if ($Hashes.sha1) { $hashObj["sha1"] = $Hashes.sha1 }
        if ($Hashes.sha512) { $hashObj["sha512"] = $Hashes.sha512 }
    }
    return [PSCustomObject]@{
        path      = "$Folder/$Filename"
        hashes    = $hashObj
        env       = [PSCustomObject]@{
            client = if ($ClientSide) { $ClientSide } else { "required" }
            server = if ($ServerSide) { $ServerSide } else { "required" }
        }
        downloads = @($Url)
        fileSize  = if ($Size) { $Size } else { 0 }
    }
}

function New-MrpackIndex {
    param([string]$Name, [string]$TargetMcVersion, [string]$LoaderName, [string]$LoaderVersion, [array]$Files)
    $dependencies = [ordered]@{ minecraft = $TargetMcVersion }
    $depKey = $MrpackDependencyKey[$LoaderName.ToLower()]
    if ($depKey -and $LoaderVersion) {
        $dependencies[$depKey] = $LoaderVersion
    }
    return [PSCustomObject]@{
        formatVersion = 1
        game          = "minecraft"
        versionId     = "1.0.0"
        name          = $Name
        files         = @($Files)
        dependencies  = $dependencies
    }
}

function Write-MrpackFile {
    param($IndexData, [string]$OutputPath)
    $json = $IndexData | ConvertTo-Json -Depth 10
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("mrpack_build_" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $indexPath = Join-Path $tempDir "modrinth.index.json"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($indexPath, $json, $utf8NoBom)
    if (Test-Path -LiteralPath $OutputPath) { Remove-Item -LiteralPath $OutputPath -Force }
    Compress-Archive -Path $indexPath -DestinationPath $OutputPath -Force
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Shared mutable state (script scope, updated from Invoke-ProcessProject)
# ---------------------------------------------------------------------------

$script:Processed = New-Object 'System.Collections.Generic.HashSet[string]'
$script:SuccessCount = 0
$script:FailedCount = 0
$script:IncompatibleCount = 0
$script:SkippedCount = 0
$script:FailedItems = @()
$script:IncompatibleItems = @()
$script:ExcludedIds = @()
$script:MrpackFiles = @()
$script:MrpackLoaderVersion = $null
$script:WorkDir = ""
$script:IncludeMods = -not $NoMods
$script:IncludeResourcepacks = -not $NoResourcepacks
$script:IncludeShaders = -not $NoShaders
$script:DownloadDepsFlag = -not $NoDeps
$script:PreferStableFlag = -not $AllowBeta
$script:TargetMcVersion = $McVersion
$script:TargetLoader = $Loader

function Test-Excluded {
    param([string]$Id)
    return $script:ExcludedIds -contains $Id
}

function Invoke-ProcessProject {
    param([string]$ProjectId, [bool]$IsDependency = $false, [string]$ParentName = "")

    if ($script:Processed.Contains($ProjectId)) { return }
    [void]$script:Processed.Add($ProjectId)

    if ((-not $IsDependency) -and (Test-Excluded $ProjectId)) {
        Write-Host "SKIPPED: $ProjectId - deselected (-Exclude)."
        $script:SkippedCount++
        return
    }

    $proj = Api-Get "/v2/project/$ProjectId"
    if (-not $proj) {
        Write-Host "FAILED: $ProjectId - $(T 'reason_project_not_found')."
        $script:FailedItems += [PSCustomObject]@{ Name = $ProjectId; Reason = (T 'reason_project_not_found') }
        $script:FailedCount++
        return
    }

    $name = $ProjectId
    if ($proj.title) { $name = $proj.title } elseif ($proj.slug) { $name = $proj.slug }
    $ptype = "mod"
    if ($proj.project_type) { $ptype = $proj.project_type }

    if (-not $IsDependency) {
        $allowed = $script:IncludeMods
        if ($ptype -eq "shader") { $allowed = $script:IncludeShaders }
        elseif ($ptype -eq "resourcepack") { $allowed = $script:IncludeResourcepacks }
        if (-not $allowed) {
            Write-Host "SKIPPED: $name - type '$ptype' is not included."
            $script:SkippedCount++
            return
        }
    }

    $versions = Api-Get "/v2/project/$ProjectId/version"
    if (-not $versions) { $versions = @() }
    $chosen = Select-Version -Versions $versions -TargetMcVersion $script:TargetMcVersion `
        -TargetLoader $script:TargetLoader -ProjectType $ptype -PreferStable $script:PreferStableFlag

    if (-not $chosen) {
        Write-Host "INCOMPATIBLE: $name - $(T 'reason_no_version')."
        $script:IncompatibleItems += [PSCustomObject]@{ Name = $name; Reason = (T 'reason_no_version') }
        $script:IncompatibleCount++
        return
    }

    if ($script:DownloadDepsFlag -and $chosen.dependencies) {
        $deps = @($chosen.dependencies | Where-Object { $_.dependency_type -eq "required" -and $_.project_id })
        foreach ($dep in $deps) {
            Invoke-ProcessProject -ProjectId $dep.project_id -IsDependency $true -ParentName $name
        }
    }

    $files = @($chosen.files)
    $fileInfo = $null
    $primary = @($files | Where-Object { $_.primary })
    if ($primary.Count -gt 0) { $fileInfo = $primary[0] }
    elseif ($files.Count -gt 0) { $fileInfo = $files[0] }

    if (-not $fileInfo) {
        Write-Host "FAILED: $name - $(T 'reason_no_file')."
        $script:FailedItems += [PSCustomObject]@{ Name = $name; Reason = (T 'reason_no_file') }
        $script:FailedCount++
        return
    }

    $loaders = @($chosen.loaders)
    $folder = Get-Category -ProjectType $ptype -Loaders $loaders
    $filename = $fileInfo.filename

    if ($Mrpack) {
        if ($MrpackSupportedFolders -notcontains $folder) {
            Write-Host "SKIPPED: $name - $folder $(T 'log_mrpack_unsupported_category')"
            $script:SkippedCount++
            return
        }
        $entry = New-MrpackFileEntry -Folder $folder -Filename $filename -Url $fileInfo.url `
            -Size $fileInfo.size -Hashes $fileInfo.hashes `
            -ClientSide $proj.client_side -ServerSide $proj.server_side
        Write-Host "OK: $name $(T 'log_mrpack_file_added')"
        $script:MrpackFiles += $entry
        $script:SuccessCount++
        return
    }

    $destPath = Join-Path $script:WorkDir (Join-Path $folder $filename)

    Write-Host "DOWNLOADING: $name -> $filename"
    if (Download-File -Url $fileInfo.url -Destination $destPath) {
        Write-Host "OK: $name saved to $folder/"
        $script:SuccessCount++
    } else {
        Write-Host "FAILED: $name - $(T 'reason_download_error')."
        $script:FailedItems += [PSCustomObject]@{ Name = $name; Reason = (T 'reason_download_error') }
        $script:FailedCount++
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

function Reset-ScriptState {
    # Resets every mutable script-scoped variable to its default. Called at
    # the top of Invoke-Main so that calling it more than once in the same
    # session (e.g. a test harness dot-sourcing this file) behaves the same
    # as a fresh process each time - which is how the script is actually
    # used in practice (one invocation, one process).
    $script:Processed = New-Object 'System.Collections.Generic.HashSet[string]'
    $script:SuccessCount = 0
    $script:FailedCount = 0
    $script:IncompatibleCount = 0
    $script:SkippedCount = 0
    $script:FailedItems = @()
    $script:IncompatibleItems = @()
    $script:ExcludedIds = @()
    $script:MrpackFiles = @()
    $script:MrpackLoaderVersion = $null
}

function Invoke-Main {
Reset-ScriptState

if ([string]::IsNullOrWhiteSpace($Collection)) {
    $Collection = Read-Host -Prompt (T 'prompt_collection')
}
if ([string]::IsNullOrWhiteSpace($Collection)) {
    Write-Host (T 'err_no_collection')
    exit 1
}

$CollectionId = Get-CollectionId $Collection

if ($ListItems) {
    Write-Host (T 'info_fetching_collection')
    $collectionJson = Api-Get "/v3/collection/$CollectionId"
    if (-not $collectionJson) {
        Write-Host (T 'err_collection_not_found')
        exit 1
    }
    $projectIds = @($collectionJson.projects)
    if ($projectIds.Count -eq 0) {
        Write-Host (T 'err_empty_collection')
        exit 1
    }
    Write-Host (T 'info_fetching_items')
    Write-Host (T 'items_header')
    $n = 0
    foreach ($projId in $projectIds) {
        $n++
        $proj = Api-Get "/v2/project/$projId"
        if ($proj) {
            $name = $projId
            if ($proj.title) { $name = $proj.title } elseif ($proj.slug) { $name = $proj.slug }
            $ptype = "mod"
            if ($proj.project_type) { $ptype = $proj.project_type }
        } else {
            $name = $projId
            $ptype = "?"
        }
        Write-Host ("  [{0}] {1}  ({2})  id={3}" -f $n, $name, $ptype, $projId)
    }
    exit 0
}

if ([string]::IsNullOrWhiteSpace($McVersion)) {
    $McVersion = Read-Host -Prompt (T 'prompt_version')
    $script:TargetMcVersion = $McVersion
}
if ([string]::IsNullOrWhiteSpace($McVersion)) {
    Write-Host (T 'err_no_version')
    exit 1
}

if ([string]::IsNullOrWhiteSpace($Loader)) {
    $Loader = Read-Host -Prompt (T 'prompt_loader')
    $script:TargetLoader = $Loader
}
if ([string]::IsNullOrWhiteSpace($Loader)) {
    Write-Host (T 'err_no_loader')
    exit 1
}

if ($Zip -and $Mrpack) {
    Write-Host "-Zip and -Mrpack can't be used together."
    exit 1
}
if ($Mrpack -and -not (Test-MrpackLoaderSupported $Loader)) {
    Write-Host (T 'err_mrpack_unsupported_loader')
    exit 1
}

if ([string]::IsNullOrWhiteSpace($Dest)) {
    $Dest = Read-Host -Prompt (T 'prompt_dest')
    if ([string]::IsNullOrWhiteSpace($Dest)) { $Dest = "." }
}

if ((-not $script:IncludeMods) -and (-not $script:IncludeResourcepacks) -and (-not $script:IncludeShaders)) {
    Write-Host (T 'err_no_category')
    exit 1
}

if (-not [string]::IsNullOrWhiteSpace($Exclude)) {
    $script:ExcludedIds = @($Exclude -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
}

if (-not $Yes) {
    Write-Host ""
    Write-Host "Collection : $Collection"
    Write-Host "MC version : $McVersion"
    Write-Host "Loader     : $Loader"
    Write-Host "Destination: $Dest"
    if ($Mrpack) { Write-Host "Save as    : mrpack" }
    elseif ($Zip) { Write-Host "Save as    : zip" }
    else { Write-Host "Save as    : folder" }
    $ans = Read-Host -Prompt (T 'prompt_confirm')
    if (-not [string]::IsNullOrWhiteSpace($ans)) {
        $firstChar = $ans.Substring(0, 1).ToLower()
        $yesChar = if ($script:LangCode -eq "pt") { "s" } else { "y" }
        if ($firstChar -ne $yesChar) {
            Write-Host (T 'info_aborted')
            exit 0
        }
    }
}

Write-Host (T 'log_start')
Write-Host (T 'info_fetching_collection')

$collectionJson = Api-Get "/v3/collection/$CollectionId"
if (-not $collectionJson) {
    Write-Host (T 'err_collection_not_found')
    exit 1
}

$projectIds = @($collectionJson.projects)
if ($projectIds.Count -eq 0) {
    Write-Host (T 'err_empty_collection')
    exit 1
}

$collectionNameRaw = $CollectionId
if ($collectionJson.name) { $collectionNameRaw = $collectionJson.name }
$collectionName = Get-SafeFilename $collectionNameRaw

Write-Host "Collection found: '$collectionNameRaw' with $($projectIds.Count) item(s)."

if ($Mrpack) {
    Write-Host (T 'log_resolving_loader_version')
    $script:MrpackLoaderVersion = Get-LatestLoaderVersion -LoaderName $Loader -TargetMcVersion $McVersion
    if ($script:MrpackLoaderVersion) {
        Write-Host "Using $Loader version $($script:MrpackLoaderVersion)."
    } else {
        Write-Host (T 'log_loader_version_unknown')
    }
}


$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("modrinth_dl_" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8))
$script:WorkDir = Join-Path $workRoot $collectionName
New-Item -ItemType Directory -Path $script:WorkDir -Force | Out-Null

foreach ($projId in $projectIds) {
    Invoke-ProcessProject -ProjectId $projId -IsDependency $false -ParentName ""
}

$outputPath = ""
try {
    if ($Mrpack) {
        Write-Host (T 'log_building_mrpack')
        if (-not (Test-Path -LiteralPath $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
        $mrpackBase = Get-UniquePath (Join-Path $Dest $collectionName) ".mrpack"
        $indexName = if ($collectionJson.name) { $collectionJson.name } else { $collectionName }
        $indexData = New-MrpackIndex -Name $indexName -TargetMcVersion $McVersion -LoaderName $Loader `
            -LoaderVersion $script:MrpackLoaderVersion -Files $script:MrpackFiles
        Write-MrpackFile -IndexData $indexData -OutputPath "$mrpackBase.mrpack"
        $outputPath = "$mrpackBase.mrpack"
    } elseif ($Zip) {
        Write-Host (T 'log_zipping')
        if (-not (Test-Path -LiteralPath $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
        $zipBase = Get-UniquePath (Join-Path $Dest $collectionName) ".zip"
        Compress-Archive -Path $script:WorkDir -DestinationPath "$zipBase.zip" -Force
        $outputPath = "$zipBase.zip"
    } else {
        Write-Host (T 'log_moving')
        if (-not (Test-Path -LiteralPath $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
        $finalDir = Get-UniquePath (Join-Path $Dest $collectionName) ""
        Move-Item -LiteralPath $script:WorkDir -Destination $finalDir -Force
        $outputPath = $finalDir
    }
} finally {
    if (Test-Path -LiteralPath $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host (T 'log_done')
Write-Host ""
Write-Host (T 'summary_header')
Write-Host "  Success: $($script:SuccessCount)   Failed: $($script:FailedCount)   Incompatible: $($script:IncompatibleCount)   Skipped: $($script:SkippedCount)"
Write-Host "$(T 'summary_output') $outputPath"

if ($script:FailedItems.Count -gt 0) {
    Write-Host ""
    Write-Host (T 'summary_failed_header')
    foreach ($item in $script:FailedItems) {
        Write-Host "  - $($item.Name): $($item.Reason)"
    }
}
if ($script:IncompatibleItems.Count -gt 0) {
    Write-Host ""
    Write-Host (T 'summary_incompatible_header')
    foreach ($item in $script:IncompatibleItems) {
        Write-Host "  - $($item.Name): $($item.Reason)"
    }
}

} # end of Invoke-Main

# Only auto-run when executed directly (not when dot-sourced, e.g. by tests).
if ($MyInvocation.InvocationName -ne '.') {
    Invoke-Main
}
