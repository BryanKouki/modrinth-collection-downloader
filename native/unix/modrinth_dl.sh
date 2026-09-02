#!/usr/bin/env bash
#
# Modrinth Collection Downloader - native Unix edition (Linux / macOS)
# =======================================================================
# A single Bash script, no Python involved at all. Uses only "curl" (to
# talk to the Modrinth API and download files) and "jq" (to read the JSON
# responses), both of which are either already on your system or a single
# package-manager command away:
#
#   Debian/Ubuntu : sudo apt install curl jq
#   Fedora        : sudo dnf install curl jq
#   Arch          : sudo pacman -S curl jq
#   macOS         : curl is preinstalled; brew install jq
#
# Written to work with the plain Bash that ships by default on macOS
# (3.2), not just modern Bash: no associative arrays, no ${var,,}.
#
# USAGE
# -----
#   ./modrinth_dl.sh
#       Fully interactive: asks for anything not passed as a flag.
#
#   ./modrinth_dl.sh -c YV97U1kk -v 1.21.1 -l fabric -d ./output --zip -y
#       Fully scripted, for automation.
#
#   ./modrinth_dl.sh -c YV97U1kk --list-items
#       Just print the collection's contents and exit.
#
# Run with -h / --help to see every option.
#
# SAFETY
# ------
# This script only queries Modrinth's public API (api.modrinth.com) and
# downloads official files hosted by Modrinth itself (cdn.modrinth.com).
# It does not collect, send, or execute anything beyond that.

set -u

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE="https://api.modrinth.com"
APP_VERSION="1.0.0"
AUTHOR="BryanKouki"
USER_AGENT="${AUTHOR}/ModrinthCollectionDownloaderShell/${APP_VERSION} (github.com/${AUTHOR})"

PLUGIN_LOADERS="bukkit spigot paper purpur folia sponge velocity waterfall bungeecord"
DATAPACK_LOADERS="datapack"

LANG_CODE="en"

# ---------------------------------------------------------------------------
# Messages (English / Portuguese)
# ---------------------------------------------------------------------------

msg() {
    local key="$1"
    if [ "$LANG_CODE" = "pt" ]; then
        case "$key" in
            prompt_collection) echo "ID ou URL da coleção: " ;;
            prompt_version) echo "Versão do Minecraft (ex: 1.21.1): " ;;
            prompt_loader) echo "Mod loader (ex: fabric, forge, neoforge, paper): " ;;
            prompt_dest) echo "Pasta de destino [.]: " ;;
            prompt_confirm) echo "Continuar com o download? [S/n]: " ;;
            err_no_collection) echo "Nenhum ID ou URL de coleção foi informado." ;;
            err_collection_not_found) echo "Coleção não encontrada ou inacessível." ;;
            err_empty_collection) echo "A coleção não tem itens." ;;
            err_no_version) echo "Nenhuma versão do Minecraft foi informada." ;;
            err_no_loader) echo "Nenhum mod loader foi informado." ;;
            err_no_category) echo "Pelo menos uma categoria precisa ficar habilitada." ;;
            err_zip_missing) echo "O comando 'zip' não foi encontrado. Instale-o (ex: sudo apt install zip) ou rode sem --zip." ;;
            err_jq_missing) echo "O comando 'jq' é necessário e não foi encontrado. Instale-o (veja o topo deste arquivo)." ;;
            err_curl_missing) echo "O comando 'curl' é necessário e não foi encontrado." ;;
            info_fetching_collection) echo "Buscando informações da coleção..." ;;
            info_fetching_items) echo "Buscando detalhes dos itens..." ;;
            info_aborted) echo "Cancelado." ;;
            items_header) echo "Itens desta coleção:" ;;
            log_start) echo "Iniciando download..." ;;
            log_zipping) echo "Compactando arquivos..." ;;
            log_moving) echo "Movendo arquivos para o destino..." ;;
            log_done) echo "Download finalizado." ;;
            reason_project_not_found) echo "não foi possível obter os dados do projeto" ;;
            reason_no_file) echo "nenhum arquivo para download foi encontrado" ;;
            reason_download_error) echo "o download falhou" ;;
            reason_no_version) echo "nenhuma versão publicada para essa versão/loader" ;;
            summary_header) echo "===== RESUMO =====" ;;
            summary_output) echo "Salvo em:" ;;
            summary_failed_header) echo "Itens que falharam:" ;;
            summary_incompatible_header) echo "Itens incompatíveis:" ;;
            yes_char) echo "s" ;;
            *) echo "$key" ;;
        esac
    else
        case "$key" in
            prompt_collection) echo "Collection ID or URL: " ;;
            prompt_version) echo "Minecraft version (e.g. 1.21.1): " ;;
            prompt_loader) echo "Mod loader (e.g. fabric, forge, neoforge, paper): " ;;
            prompt_dest) echo "Destination folder [.]: " ;;
            prompt_confirm) echo "Proceed with the download? [Y/n]: " ;;
            err_no_collection) echo "No collection ID or URL was given." ;;
            err_collection_not_found) echo "Collection not found or inaccessible." ;;
            err_empty_collection) echo "The collection has no items." ;;
            err_no_version) echo "No Minecraft version was given." ;;
            err_no_loader) echo "No mod loader was given." ;;
            err_no_category) echo "At least one category must be left enabled." ;;
            err_zip_missing) echo "The 'zip' command was not found. Install it (e.g. sudo apt install zip) or run without --zip." ;;
            err_jq_missing) echo "The 'jq' command is required and was not found. Install it (see the top of this file)." ;;
            err_curl_missing) echo "The 'curl' command is required and was not found." ;;
            info_fetching_collection) echo "Fetching collection information..." ;;
            info_fetching_items) echo "Fetching item details..." ;;
            info_aborted) echo "Aborted." ;;
            items_header) echo "Items in this collection:" ;;
            log_start) echo "Starting download..." ;;
            log_zipping) echo "Zipping files..." ;;
            log_moving) echo "Moving files to the destination..." ;;
            log_done) echo "Download finished." ;;
            reason_project_not_found) echo "could not fetch the project's details" ;;
            reason_no_file) echo "no downloadable file was found" ;;
            reason_download_error) echo "the download failed" ;;
            reason_no_version) echo "no version published for that Minecraft version/loader" ;;
            summary_header) echo "===== SUMMARY =====" ;;
            summary_output) echo "Saved to:" ;;
            summary_failed_header) echo "Failed items:" ;;
            summary_incompatible_header) echo "Incompatible items:" ;;
            yes_char) echo "y" ;;
            *) echo "$key" ;;
        esac
    fi
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

api_get() {
    # $1 = API path (e.g. /v2/project/sodium). Prints JSON, or nothing on failure.
    curl -fsSL --max-time 20 -H "User-Agent: $USER_AGENT" -H "Accept: application/json" \
        "${API_BASE}${1}" 2>/dev/null
}

download_file() {
    # $1 = URL, $2 = destination path. Returns 0 on success.
    local url="$1" dest="$2" tmp
    tmp="${dest}.part"
    mkdir -p "$(dirname "$dest")"
    if curl -fsSL --max-time 60 -H "User-Agent: $USER_AGENT" -o "$tmp" "$url" 2>/dev/null; then
        if [ -s "$tmp" ]; then
            mv -f "$tmp" "$dest"
            return 0
        fi
    fi
    rm -f "$tmp" 2>/dev/null
    return 1
}

extract_collection_id() {
    local input="$1" extracted
    extracted=$(printf '%s' "$input" | sed -n 's#.*modrinth\.com/collection/\([^/?#]*\).*#\1#p')
    if [ -n "$extracted" ]; then
        printf '%s' "$extracted"
    else
        printf '%s' "$input"
    fi
}

sanitize_filename() {
    printf '%s' "$1" | sed -e 's/[<>:"/\\|?*]/_/g' -e 's/[[:space:]]*$//'
}

unique_path() {
    # $1 = base path, $2 = suffix (e.g. ".zip" or ""). Prints a path that doesn't exist yet.
    local base="$1" suffix="$2" candidate="$1" i=2
    while [ -e "${candidate}${suffix}" ]; do
        candidate="${base} (${i})"
        i=$((i + 1))
    done
    printf '%s' "$candidate"
}

# ---------------------------------------------------------------------------
# Categorization / version selection
# ---------------------------------------------------------------------------

list_intersects() {
    # $1 = space-separated list, $2 = space-separated list. True if they share a word.
    local w
    for w in $1; do
        case " $2 " in
            *" $w "*) return 0 ;;
        esac
    done
    return 1
}

categorize() {
    # $1 = project_type, $2 = space-separated lowercase loaders
    local ptype="$1" loaders="$2"
    case "$ptype" in
        shader) echo "shaderpacks"; return ;;
        resourcepack) echo "resourcepacks"; return ;;
    esac
    if list_intersects "$loaders" "$DATAPACK_LOADERS"; then echo "datapacks"; return; fi
    if list_intersects "$loaders" "$PLUGIN_LOADERS"; then echo "plugins"; return; fi
    echo "mods"
}

select_version() {
    # $1 = versions JSON array, $2 = mc version, $3 = loader, $4 = project_type, $5 = prefer_stable (1/0)
    # Prints the chosen version's JSON object (compact) on success, nothing on failure.
    local versions_json="$1" mcv="$2" loader="$3" ptype="$4" prefer_stable="$5"
    local rl same_mcv candidates count sorted

    rl=$(printf '%s' "$loader" | tr '[:upper:]' '[:lower:]')
    same_mcv=$(printf '%s' "$versions_json" | jq --arg mcv "$mcv" '[.[] | select((.game_versions // []) | index($mcv))]')

    case "$ptype" in
        resourcepack)
            candidates=$(printf '%s' "$same_mcv" | jq \
                '[.[] | select((((.loaders // []) | length) == 0) or ((.loaders // []) | map(ascii_downcase) | index("minecraft") != null))]')
            ;;
        shader)
            candidates="$same_mcv"
            ;;
        *)
            local exact exact_count
            exact=$(printf '%s' "$same_mcv" | jq --arg rl "$rl" '[.[] | select(((.loaders // []) | map(ascii_downcase) | index($rl)) != null)]')
            exact_count=$(printf '%s' "$exact" | jq 'length')
            if [ "$exact_count" -gt 0 ]; then
                candidates="$exact"
            else
                candidates=$(printf '%s' "$same_mcv" | jq \
                    --argjson special '["bukkit","spigot","paper","purpur","folia","sponge","velocity","waterfall","bungeecord","datapack"]' \
                    '[.[] | select((((.loaders // []) | map(ascii_downcase)) - $special | length) < ((.loaders // []) | length))]')
            fi
            ;;
    esac

    count=$(printf '%s' "$candidates" | jq 'length')
    [ "$count" -eq 0 ] && return 1

    sorted=$(printf '%s' "$candidates" | jq 'sort_by(.date_published) | reverse')

    if [ "$prefer_stable" = "1" ]; then
        local releases rel_count
        releases=$(printf '%s' "$sorted" | jq '[.[] | select(.version_type == "release")]')
        rel_count=$(printf '%s' "$releases" | jq 'length')
        if [ "$rel_count" -gt 0 ]; then
            printf '%s' "$releases" | jq -c '.[0]'
            return 0
        fi
    fi
    printf '%s' "$sorted" | jq -c '.[0]'
    return 0
}

# ---------------------------------------------------------------------------
# Global state (set by main/parse_args, mutated by process_project)
# ---------------------------------------------------------------------------

COLLECTION_INPUT=""
MC_VERSION=""
LOADER=""
DEST=""
SAVE_AS_ZIP=0
INCLUDE_MODS=1
INCLUDE_RESOURCEPACKS=1
INCLUDE_SHADERS=1
DOWNLOAD_DEPS=1
PREFER_STABLE=1
EXCLUDE_RAW=""
LIST_ITEMS_ONLY=0
ASSUME_YES=0

PROCESSED=" "
SUCCESS_COUNT=0
FAILED_COUNT=0
INCOMPATIBLE_COUNT=0
SKIPPED_COUNT=0
FAILED_LINES=""
INCOMPATIBLE_LINES=""
EXCLUDED_IDS=" "
WORK_DIR=""

print_help() {
    cat <<'HELP'
Modrinth Collection Downloader - native Unix edition

Usage: modrinth_dl.sh [options]

  -c, --collection ID_OR_URL   Collection ID or URL
  -v, --mc-version VERSION     Minecraft version (e.g. 1.21.1)
  -l, --loader LOADER          Mod loader (e.g. fabric, forge, neoforge, paper)
  -d, --dest PATH              Destination folder (default: current directory)
      --zip                    Save as a single .zip instead of a folder
      --no-mods                Exclude mods, plugins and datapacks
      --no-resourcepacks       Exclude resource/texture packs
      --no-shaders             Exclude shaders
      --no-deps                Do not download required dependencies
      --allow-beta             Do not prefer stable releases
      --exclude ID1,ID2,...    Comma-separated project IDs/slugs to exclude
      --list-items             Print the collection's items and exit
      --lang en|pt             Output language (default: en)
  -y, --yes                    Skip the confirmation prompt
  -h, --help                   Show this help and exit

Examples:
  ./modrinth_dl.sh
  ./modrinth_dl.sh -c YV97U1kk -v 1.21.1 -l fabric -d ./out --zip -y
  ./modrinth_dl.sh -c YV97U1kk --list-items
HELP
}

is_excluded() {
    case "$EXCLUDED_IDS" in
        *" $1 "*) return 0 ;;
    esac
    return 1
}

is_processed() {
    case "$PROCESSED" in
        *" $1 "*) return 0 ;;
    esac
    return 1
}
mark_processed() { PROCESSED="${PROCESSED}${1} "; }

# process_project ID IS_DEPENDENCY PARENT_NAME
process_project() {
    local pid="$1" is_dep="$2" parent="$3"

    is_processed "$pid" && return
    mark_processed "$pid"

    if [ "$is_dep" != "1" ] && is_excluded "$pid"; then
        echo "SKIPPED: ${pid} - deselected (--exclude)."
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        return
    fi

    local proj name ptype
    proj=$(api_get "/v2/project/${pid}")
    if [ -z "$proj" ]; then
        echo "FAILED: ${pid} - $(msg reason_project_not_found)."
        FAILED_LINES="${FAILED_LINES}${pid}	$(msg reason_project_not_found)
"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        return
    fi
    name=$(printf '%s' "$proj" | jq -r '.title // .slug // "?"')
    ptype=$(printf '%s' "$proj" | jq -r '.project_type // "mod"')

    if [ "$is_dep" != "1" ]; then
        local allowed=1
        case "$ptype" in
            shader) [ "$INCLUDE_SHADERS" = "1" ] || allowed=0 ;;
            resourcepack) [ "$INCLUDE_RESOURCEPACKS" = "1" ] || allowed=0 ;;
            *) [ "$INCLUDE_MODS" = "1" ] || allowed=0 ;;
        esac
        if [ "$allowed" = "0" ]; then
            echo "SKIPPED: ${name} - type '${ptype}' is not included."
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            return
        fi
    fi

    local versions chosen
    versions=$(api_get "/v2/project/${pid}/version")
    [ -z "$versions" ] && versions="[]"
    if ! chosen=$(select_version "$versions" "$MC_VERSION" "$LOADER" "$ptype" "$PREFER_STABLE"); then
        echo "INCOMPATIBLE: ${name} - $(msg reason_no_version)."
        INCOMPATIBLE_LINES="${INCOMPATIBLE_LINES}${name}	$(msg reason_no_version)
"
        INCOMPATIBLE_COUNT=$((INCOMPATIBLE_COUNT + 1))
        return
    fi

    if [ "$DOWNLOAD_DEPS" = "1" ]; then
        local dep_ids
        dep_ids=$(printf '%s' "$chosen" | jq -r '.dependencies[]? | select(.dependency_type == "required" and (.project_id != null)) | .project_id')
        if [ -n "$dep_ids" ]; then
            while IFS= read -r dep_id; do
                [ -n "$dep_id" ] && process_project "$dep_id" "1" "$name"
            done <<< "$dep_ids"
        fi
    fi

    local file_url file_name loaders_lc folder dest_path
    file_url=$(printf '%s' "$chosen" | jq -r '([.files[]? | select(.primary)] + .files)[0].url // empty')
    file_name=$(printf '%s' "$chosen" | jq -r '([.files[]? | select(.primary)] + .files)[0].filename // empty')
    if [ -z "$file_url" ] || [ -z "$file_name" ]; then
        echo "FAILED: ${name} - $(msg reason_no_file)."
        FAILED_LINES="${FAILED_LINES}${name}	$(msg reason_no_file)
"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        return
    fi

    loaders_lc=$(printf '%s' "$chosen" | jq -r '(.loaders // []) | map(ascii_downcase) | join(" ")')
    folder=$(categorize "$ptype" "$loaders_lc")
    dest_path="${WORK_DIR}/${folder}/${file_name}"

    echo "DOWNLOADING: ${name} -> ${file_name}"
    if download_file "$file_url" "$dest_path"; then
        echo "OK: ${name} saved to ${folder}/"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "FAILED: ${name} - $(msg reason_download_error)."
        FAILED_LINES="${FAILED_LINES}${name}	$(msg reason_download_error)
"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -c|--collection) COLLECTION_INPUT="$2"; shift 2 ;;
            -v|--mc-version) MC_VERSION="$2"; shift 2 ;;
            -l|--loader) LOADER="$2"; shift 2 ;;
            -d|--dest) DEST="$2"; shift 2 ;;
            --zip) SAVE_AS_ZIP=1; shift ;;
            --no-mods) INCLUDE_MODS=0; shift ;;
            --no-resourcepacks) INCLUDE_RESOURCEPACKS=0; shift ;;
            --no-shaders) INCLUDE_SHADERS=0; shift ;;
            --no-deps) DOWNLOAD_DEPS=0; shift ;;
            --allow-beta) PREFER_STABLE=0; shift ;;
            --exclude) EXCLUDE_RAW="$2"; shift 2 ;;
            --list-items) LIST_ITEMS_ONLY=1; shift ;;
            --lang) LANG_CODE="$2"; shift 2 ;;
            -y|--yes) ASSUME_YES=1; shift ;;
            -h|--help) print_help; exit 0 ;;
            *) echo "Unknown option: $1" >&2; print_help; exit 1 ;;
        esac
    done
}

reset_state() {
    # Resets all mutable globals to their defaults. Called at the top of
    # main() so that calling main() more than once in the same shell (e.g.
    # from a test harness that sources this file) behaves the same as a
    # fresh process each time - which is how the script is actually used
    # in practice (one invocation, one process).
    COLLECTION_INPUT=""
    MC_VERSION=""
    LOADER=""
    DEST=""
    SAVE_AS_ZIP=0
    INCLUDE_MODS=1
    INCLUDE_RESOURCEPACKS=1
    INCLUDE_SHADERS=1
    DOWNLOAD_DEPS=1
    PREFER_STABLE=1
    EXCLUDE_RAW=""
    LIST_ITEMS_ONLY=0
    ASSUME_YES=0
    LANG_CODE="en"

    PROCESSED=" "
    SUCCESS_COUNT=0
    FAILED_COUNT=0
    INCOMPATIBLE_COUNT=0
    SKIPPED_COUNT=0
    FAILED_LINES=""
    INCOMPATIBLE_LINES=""
    EXCLUDED_IDS=" "
    WORK_DIR=""
}

main() {
    reset_state
    parse_args "$@"

    if ! command -v curl >/dev/null 2>&1; then
        echo "$(msg err_curl_missing)" >&2
        exit 1
    fi
    if ! command -v jq >/dev/null 2>&1; then
        echo "$(msg err_jq_missing)" >&2
        exit 1
    fi
    if [ "$SAVE_AS_ZIP" = "1" ] && ! command -v zip >/dev/null 2>&1; then
        echo "$(msg err_zip_missing)" >&2
        exit 1
    fi

    if [ -z "$COLLECTION_INPUT" ]; then
        printf '%s' "$(msg prompt_collection)"
        read -r COLLECTION_INPUT
    fi
    if [ -z "$COLLECTION_INPUT" ]; then
        echo "$(msg err_no_collection)"
        exit 1
    fi

    local collection_id
    collection_id=$(extract_collection_id "$COLLECTION_INPUT")

    if [ "$LIST_ITEMS_ONLY" = "1" ]; then
        echo "$(msg info_fetching_collection)"
        local collection_json project_ids
        collection_json=$(api_get "/v3/collection/${collection_id}")
        if [ -z "$collection_json" ]; then
            echo "$(msg err_collection_not_found)"
            exit 1
        fi
        project_ids=$(printf '%s' "$collection_json" | jq -r '.projects[]?')
        if [ -z "$project_ids" ]; then
            echo "$(msg err_empty_collection)"
            exit 1
        fi
        echo "$(msg info_fetching_items)"
        echo "$(msg items_header)"
        local n=0 pid proj name ptype
        while IFS= read -r pid; do
            [ -z "$pid" ] && continue
            n=$((n + 1))
            proj=$(api_get "/v2/project/${pid}")
            if [ -n "$proj" ]; then
                name=$(printf '%s' "$proj" | jq -r '.title // .slug // "?"')
                ptype=$(printf '%s' "$proj" | jq -r '.project_type // "mod"')
            else
                name="$pid"
                ptype="?"
            fi
            printf '  [%d] %s  (%s)  id=%s\n' "$n" "$name" "$ptype" "$pid"
        done <<< "$project_ids"
        return 0
    fi

    if [ -z "$MC_VERSION" ]; then
        printf '%s' "$(msg prompt_version)"
        read -r MC_VERSION
    fi
    [ -z "$MC_VERSION" ] && { echo "$(msg err_no_version)"; exit 1; }

    if [ -z "$LOADER" ]; then
        printf '%s' "$(msg prompt_loader)"
        read -r LOADER
    fi
    [ -z "$LOADER" ] && { echo "$(msg err_no_loader)"; exit 1; }

    if [ -z "$DEST" ]; then
        printf '%s' "$(msg prompt_dest)"
        read -r DEST
        [ -z "$DEST" ] && DEST="."
    fi

    if [ "$INCLUDE_MODS" = "0" ] && [ "$INCLUDE_RESOURCEPACKS" = "0" ] && [ "$INCLUDE_SHADERS" = "0" ]; then
        echo "$(msg err_no_category)"
        exit 1
    fi

    if [ -n "$EXCLUDE_RAW" ]; then
        local old_ifs id
        old_ifs="$IFS"
        IFS=','
        for id in $EXCLUDE_RAW; do
            EXCLUDED_IDS="${EXCLUDED_IDS}${id} "
        done
        IFS="$old_ifs"
    fi

    if [ "$ASSUME_YES" != "1" ]; then
        echo ""
        echo "Collection : $COLLECTION_INPUT"
        echo "MC version : $MC_VERSION"
        echo "Loader     : $LOADER"
        echo "Destination: $DEST"
        if [ "$SAVE_AS_ZIP" = "1" ]; then echo "Save as    : zip"; else echo "Save as    : folder"; fi
        printf '%s' "$(msg prompt_confirm)"
        local ans first_char
        read -r ans
        if [ -n "$ans" ]; then
            first_char=$(printf '%s' "$ans" | cut -c1 | tr '[:upper:]' '[:lower:]')
            if [ "$first_char" != "$(msg yes_char)" ]; then
                echo "$(msg info_aborted)"
                exit 0
            fi
        fi
    fi

    echo "$(msg log_start)"
    echo "$(msg info_fetching_collection)"

    local collection_json project_ids collection_name_raw collection_name item_count work_root
    collection_json=$(api_get "/v3/collection/${collection_id}")
    if [ -z "$collection_json" ]; then
        echo "$(msg err_collection_not_found)"
        exit 1
    fi

    project_ids=$(printf '%s' "$collection_json" | jq -r '.projects[]?')
    if [ -z "$project_ids" ]; then
        echo "$(msg err_empty_collection)"
        exit 1
    fi

    collection_name_raw=$(printf '%s' "$collection_json" | jq -r '.name // empty')
    [ -z "$collection_name_raw" ] && collection_name_raw="$collection_id"
    collection_name=$(sanitize_filename "$collection_name_raw")
    [ -z "$collection_name" ] && collection_name="modrinth-collection"

    item_count=$(printf '%s\n' "$project_ids" | grep -c .)
    echo "Collection found: '${collection_name_raw}' with ${item_count} item(s)."

    work_root=$(mktemp -d)
    WORK_DIR="${work_root}/${collection_name}"
    mkdir -p "$WORK_DIR"

    local pid
    while IFS= read -r pid; do
        [ -n "$pid" ] && process_project "$pid" "0" ""
    done <<< "$project_ids"

    local output_path
    if [ "$SAVE_AS_ZIP" = "1" ]; then
        echo "$(msg log_zipping)"
        mkdir -p "$DEST"
        local zip_base
        zip_base=$(unique_path "${DEST%/}/${collection_name}" ".zip")
        ( cd "$work_root" && zip -rq "${zip_base}.zip" "$collection_name" )
        output_path="${zip_base}.zip"
    else
        echo "$(msg log_moving)"
        mkdir -p "$DEST"
        local final_dir
        final_dir=$(unique_path "${DEST%/}/${collection_name}" "")
        mv "$WORK_DIR" "$final_dir"
        output_path="$final_dir"
    fi
    rm -rf "$work_root"

    echo "$(msg log_done)"
    echo ""
    echo "$(msg summary_header)"
    echo "  Success: ${SUCCESS_COUNT}   Failed: ${FAILED_COUNT}   Incompatible: ${INCOMPATIBLE_COUNT}   Skipped: ${SKIPPED_COUNT}"
    echo "$(msg summary_output) ${output_path}"

    if [ -n "$FAILED_LINES" ]; then
        echo ""
        echo "$(msg summary_failed_header)"
        while IFS="$(printf '\t')" read -r n r; do
            [ -n "$n" ] && echo "  - ${n}: ${r}"
        done <<< "$FAILED_LINES"
    fi
    if [ -n "$INCOMPATIBLE_LINES" ]; then
        echo ""
        echo "$(msg summary_incompatible_header)"
        while IFS="$(printf '\t')" read -r n r; do
            [ -n "$n" ] && echo "  - ${n}: ${r}"
        done <<< "$INCOMPATIBLE_LINES"
    fi
}

# Only auto-run when executed directly (not when sourced, e.g. by tests).
if [ "${BASH_SOURCE[0]:-$0}" = "${0}" ]; then
    main "$@"
fi
