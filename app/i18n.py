"""
Simple internationalization (EN / PT-BR) for the interface.

Usage:
    from .i18n import t
    t("app_title")                       # no parameters
    t("collection_found", name=x, n=3)   # with parameters ({name} and {n} in the text)

The translated string values themselves stay in their target language (that
is their whole purpose) — only the surrounding code and comments are English.
"""

from typing import Dict

DEFAULT_LANG = "en"

_PT: Dict[str, str] = {
    # Header
    "app_title": "Modrinth Collection Downloader",
    "app_subtitle": "Baixe todos os mods de uma coleção do Modrinth — direto no seu computador.",
    "btn_lang": "EN",
    "btn_guide": "Guia",

    # Form
    "label_collection": "ID OU URL DA COLEÇÃO",
    "placeholder_collection": "ex: YV97U1kk ou https://modrinth.com/collection/YV97U1kk",
    "btn_fetch_items": "Carregar Itens",
    "btn_fetch_items_loading": "Carregando...",

    "label_items": "ITENS DESTA COLEÇÃO",
    "items_placeholder": "Carregue a coleção acima para ver e escolher os itens individualmente.",
    "items_count": "{count} itens carregados",
    "btn_select_all": "Marcar tudo",
    "btn_select_none": "Desmarcar tudo",
    "group_mods": "Mods e Modpacks",
    "group_resourcepacks": "Resource/Texture Packs",
    "group_shaders": "Shaders",
    "label_mc_version": "VERSÃO DO MINECRAFT",
    "placeholder_mc_version": "Selecione ou digite uma versão...",
    "label_loader": "MOD LOADER",
    "placeholder_loader": "Selecione ou digite um loader...",
    "hint_editable": "Você também pode digitar um valor que não esteja na lista.",

    "label_include": "TIPOS DE CONTEÚDO",
    "chk_mods": "Mods, Plugins e Datapacks",
    "chk_resourcepacks": "Resource/Texture Packs",
    "chk_shaders": "Shaders",

    "label_dependencies": "DEPENDÊNCIAS",
    "chk_dependencies": "Baixar dependências obrigatórias de cada mod",

    "label_release_pref": "PREFERÊNCIA DE VERSÃO",
    "chk_prefer_stable": "Preferir versões estáveis (release) a alpha/beta mais recentes",

    "label_save_options": "ONDE SALVAR",
    "radio_save_folder": "Pasta com os arquivos organizados",
    "radio_save_zip": "Arquivo .zip",
    "btn_choose_folder": "Escolher pasta de destino...",
    "label_destination": "Destino:",
    "placeholder_destination": "Nenhuma pasta selecionada",
    "hint_output_name": "O resultado será salvo com o nome da coleção.",

    "btn_download": "Baixar Coleção",
    "btn_downloading": "Baixando...",
    "btn_cancel": "Cancelar",

    "label_log": "Registro de atividade",
    "btn_clear_log": "Limpar",
    "btn_show_log": "Mostrar",
    "btn_hide_log": "Ocultar",

    "label_results": "RESUMO",
    "results_success": "Sucesso",
    "results_failed": "Falharam",
    "results_incompatible": "Incompatíveis",
    "results_skipped": "Ignorados",

    "details_empty": "Nenhum item com falha ou incompatível até agora.",
    "details_more": "...e mais {count}",

    "footer_made_by": "Feito por {author}",
    "footer_star": "Se curtir, deixe uma estrela no GitHub",
    "footer_powered": "Powered by the Modrinth API. Todos os downloads acontecem no seu computador.",
    "footer_version": "v{version}",

    # Validation / error messages
    "msg_error_title": "Erro",
    "msg_error_no_collection": "Informe o ID ou a URL da coleção.",
    "msg_error_no_version": "Informe a versão do Minecraft.",
    "msg_error_no_loader": "Informe o mod loader.",
    "msg_error_no_category": "Selecione ao menos um tipo de conteúdo para incluir no download.",
    "msg_error_no_items_selected": "Selecione ao menos um item na lista para baixar.",
    "msg_error_no_destination": "Escolha uma pasta de destino.",
    "msg_error_collection_not_found": "Coleção '{id}' não encontrada ou inacessível.",
    "msg_error_empty_collection": "A coleção '{id}' não contém nenhum item.",
    "msg_error_unexpected": "Ocorreu um erro inesperado: {error}",

    "msg_done_title": "Concluído",
    "msg_done_text": "Download finalizado!\n\nSucesso: {success}\nFalharam: {failed}\nIncompatíveis: {incompatible}\nIgnorados: {skipped}\n\nSalvo em:\n{path}",
    "msg_done_failed_header": "Itens que falharam:",
    "msg_done_incompatible_header": "Itens incompatíveis:",

    # Log
    "log_start": "Iniciando download da coleção '{id}'...",
    "log_fetching_collection": "Buscando informações da coleção...",
    "log_collection_found": "Coleção encontrada: '{name}' com {count} item(ns).",
    "log_fetching_project": "Consultando projeto {id}...",
    "log_project_not_found": "FALHA: não foi possível obter informações do projeto {id} (removido ou erro de rede).",
    "log_project_skipped_category": "IGNORADO: {name} — tipo '{type}' não está marcado para download.",
    "log_project_skipped_selection": "IGNORADO: {name} — desmarcado na lista de itens.",
    "log_no_version_found": "INCOMPATÍVEL: {name} — nenhuma versão encontrada para Minecraft {version} / loader {loader}.",
    "log_downloading": "BAIXANDO: {name} -> {filename}",
    "log_download_success": "OK: {name} salvo em {folder}/",
    "log_download_failed": "FALHA: não foi possível baixar {name}.",
    "log_dependency_of": "  [DEPENDÊNCIA de {parent}] {message}",
    "log_processing_dependencies": "Processando {count} dependência(s) obrigatória(s) de {name}...",
    "log_zipping": "Compactando arquivos em {name}.zip...",
    "log_moving": "Movendo arquivos para {path}...",
    "log_cleanup_error": "Aviso: não foi possível limpar arquivos temporários: {error}",
    "log_done": "Download finalizado.",
    "log_cancelled": "Download cancelado pelo usuário.",
    "log_error_unexpected": "ERRO inesperado ao processar {name}: {error}",

    # Reasons shown in the end-of-download failure/incompatibility summary
    "reason_project_not_found": "Não foi possível obter os dados do projeto (removido, ou erro de rede).",
    "reason_no_file": "Nenhum arquivo para download foi encontrado nessa versão.",
    "reason_download_error": "O download falhou (erro de rede ou não foi possível salvar o arquivo).",
    "reason_no_version": "Nenhuma versão publicada para Minecraft {version} com o loader {loader}.",

    "status_idle": "Pronto para começar.",
    "status_running": "Baixando coleção...",
    "status_done": "Concluído.",
    "status_error": "Erro.",
    "status_cancelled": "Cancelado.",

    # Guide
    "guide_title": "Guia — Modrinth Collection Downloader",
    "guide_text": (
        "COMO USAR\n"
        "1. Cole o ID ou a URL de uma coleção pública do Modrinth (ex: https://modrinth.com/collection/XXXXXXX).\n"
        "2. Clique em 'Carregar Itens' para ver cada mod/resource pack/shader da coleção individualmente, com uma "
        "caixinha de marcação — tudo vem marcado por padrão. Desmarque o que não quiser baixar (esse passo é "
        "opcional: sem clicar aqui, o download usa só os filtros de categoria do passo 4).\n"
        "3. Escolha a versão do Minecraft e o mod loader. Se a versão/loader que você precisa ainda não estiver "
        "na lista (ex.: acabou de ser lançada), basta digitá-la manualmente no campo.\n"
        "4. Marque o que você quer incluir no download: Mods/Plugins/Datapacks, Resource/Texture Packs e/ou Shaders "
        "(marcar/desmarcar aqui também marca/desmarca todos os itens dessa categoria na lista individual, se "
        "ela já tiver sido carregada).\n"
        "5. Se quiser, ative 'Baixar dependências' para que dependências obrigatórias de cada mod também sejam baixadas.\n"
        "6. Escolha se prefere sempre a versão release mais recente (mais estável) ou a versão mais nova disponível, "
        "mesmo que seja alpha/beta.\n"
        "7. Escolha se quer os arquivos numa pasta organizada ou compactados num único .zip, e selecione a pasta de destino.\n"
        "8. Clique em 'Baixar Coleção' e acompanhe o progresso — o botão 'Cancelar' fica disponível durante o download.\n\n"
        "ORGANIZAÇÃO DAS PASTAS\n"
        "O programa separa automaticamente os arquivos baixados em subpastas, de acordo com o tipo detectado "
        "pela própria API do Modrinth e pelo loader da versão baixada:\n"
        "  • mods/          -> mods para Fabric, Forge, NeoForge, Quilt etc.\n"
        "  • resourcepacks/ -> resource packs e texture packs (o Modrinth não diferencia oficialmente os dois tipos)\n"
        "  • shaderpacks/   -> shaders\n"
        "  • plugins/       -> plugins de servidor (Bukkit, Spigot, Paper, Purpur, Folia, Sponge, Velocity, etc.)\n"
        "  • datapacks/     -> datapacks\n\n"
        "RESULTADOS\n"
        "  • Sucesso: o arquivo foi baixado normalmente.\n"
        "  • Falharam: houve um erro de rede/gravação ao tentar baixar o arquivo.\n"
        "  • Incompatíveis: o mod existe, mas não tem nenhuma versão publicada para a combinação de "
        "versão do Minecraft + loader escolhida.\n"
        "  • Ignorados: itens fora dos filtros marcados em 'Incluir no download', ou desmarcados manualmente "
        "na lista de itens.\n\n"
        "SOBRE SEGURANÇA\n"
        "O programa apenas consulta a API pública do Modrinth (api.modrinth.com) e baixa os arquivos oficiais "
        "hospedados pelo próprio Modrinth (cdn.modrinth.com). Nenhum outro dado é enviado, coletado ou executado."
    ),
    "btn_close": "Fechar",
}

_EN: Dict[str, str] = {
    # Header
    "app_title": "Modrinth Collection Downloader",
    "app_subtitle": "Download all mods from a Modrinth collection — entirely on your computer.",
    "btn_lang": "PT",
    "btn_guide": "Guide",

    # Form
    "label_collection": "COLLECTION ID OR URL",
    "placeholder_collection": "e.g. YV97U1kk or https://modrinth.com/collection/YV97U1kk",
    "btn_fetch_items": "Load Items",
    "btn_fetch_items_loading": "Loading...",

    "label_items": "ITEMS IN THIS COLLECTION",
    "items_placeholder": "Load the collection above to see and choose individual items.",
    "items_count": "{count} items loaded",
    "btn_select_all": "Select all",
    "btn_select_none": "Select none",
    "group_mods": "Mods & Modpacks",
    "group_resourcepacks": "Resource/Texture Packs",
    "group_shaders": "Shaders",
    "label_mc_version": "MINECRAFT VERSION",
    "placeholder_mc_version": "Select or type a version...",
    "label_loader": "MOD LOADER",
    "placeholder_loader": "Select or type a loader...",
    "hint_editable": "You can also type a value that isn't in the list.",

    "label_include": "CONTENT TO DOWNLOAD",
    "chk_mods": "Mods, Plugins & Datapacks",
    "chk_resourcepacks": "Resource/Texture Packs",
    "chk_shaders": "Shaders",

    "label_dependencies": "DEPENDENCIES",
    "chk_dependencies": "Download required dependencies for each mod",

    "label_release_pref": "RELEASE PREFERENCE",
    "chk_prefer_stable": "Prefer stable releases over newest alpha/beta",

    "label_save_options": "WHERE TO SAVE",
    "radio_save_folder": "Folder with organized files",
    "radio_save_zip": ".zip file",
    "btn_choose_folder": "Choose destination folder...",
    "label_destination": "Destination:",
    "placeholder_destination": "No folder selected",
    "hint_output_name": "The result will be saved using the collection's name.",

    "btn_download": "Download Collection",
    "btn_downloading": "Downloading...",
    "btn_cancel": "Cancel",

    "label_log": "Activity log",
    "btn_clear_log": "Clear",
    "btn_show_log": "Show",
    "btn_hide_log": "Hide",

    "label_results": "SUMMARY",
    "results_success": "Success",
    "results_failed": "Failed",
    "results_incompatible": "Incompatible",
    "results_skipped": "Skipped",

    "details_empty": "No failed or incompatible items so far.",
    "details_more": "...and {count} more",

    "footer_made_by": "Made by {author}",
    "footer_star": "Please, give me a star on GitHub",
    "footer_powered": "Powered by the Modrinth API. All downloads happen on your computer.",
    "footer_version": "v{version}",

    # Validation / error messages
    "msg_error_title": "Error",
    "msg_error_no_collection": "Enter the collection ID or URL.",
    "msg_error_no_version": "Enter the Minecraft version.",
    "msg_error_no_loader": "Enter the mod loader.",
    "msg_error_no_category": "Select at least one content type to include in the download.",
    "msg_error_no_items_selected": "Select at least one item in the list to download.",
    "msg_error_no_destination": "Choose a destination folder.",
    "msg_error_collection_not_found": "Collection '{id}' not found or inaccessible.",
    "msg_error_empty_collection": "Collection '{id}' contains no items.",
    "msg_error_unexpected": "An unexpected error occurred: {error}",

    "msg_done_title": "Done",
    "msg_done_text": "Download finished!\n\nSuccess: {success}\nFailed: {failed}\nIncompatible: {incompatible}\nSkipped: {skipped}\n\nSaved to:\n{path}",
    "msg_done_failed_header": "Failed items:",
    "msg_done_incompatible_header": "Incompatible items:",

    # Log
    "log_start": "Starting download of collection '{id}'...",
    "log_fetching_collection": "Fetching collection information...",
    "log_collection_found": "Collection found: '{name}' with {count} item(s).",
    "log_fetching_project": "Fetching project {id}...",
    "log_project_not_found": "FAILED: could not fetch info for project {id} (removed or network error).",
    "log_project_skipped_category": "SKIPPED: {name} — type '{type}' is not checked for download.",
    "log_project_skipped_selection": "SKIPPED: {name} — unchecked in the items list.",
    "log_no_version_found": "INCOMPATIBLE: {name} — no version found for Minecraft {version} / loader {loader}.",
    "log_downloading": "DOWNLOADING: {name} -> {filename}",
    "log_download_success": "OK: {name} saved to {folder}/",
    "log_download_failed": "FAILED: could not download {name}.",
    "log_dependency_of": "  [DEPENDENCY of {parent}] {message}",
    "log_processing_dependencies": "Processing {count} required dependency(ies) of {name}...",
    "log_zipping": "Zipping files into {name}.zip...",
    "log_moving": "Moving files to {path}...",
    "log_cleanup_error": "Warning: could not clean up temporary files: {error}",
    "log_done": "Download finished.",
    "log_cancelled": "Download cancelled by user.",
    "log_error_unexpected": "Unexpected ERROR while processing {name}: {error}",

    # Reasons shown in the end-of-download failure/incompatibility summary
    "reason_project_not_found": "Could not fetch the project's details (it may have been removed, or a network error occurred).",
    "reason_no_file": "No downloadable file was found for this version.",
    "reason_download_error": "The download failed (network error, or the file could not be saved).",
    "reason_no_version": "No version published for Minecraft {version} with the {loader} loader.",

    "status_idle": "Ready to start.",
    "status_running": "Downloading collection...",
    "status_done": "Done.",
    "status_error": "Error.",
    "status_cancelled": "Cancelled.",

    # Guide
    "guide_title": "Guide — Modrinth Collection Downloader",
    "guide_text": (
        "HOW TO USE\n"
        "1. Paste the ID or URL of a public Modrinth collection (e.g. https://modrinth.com/collection/XXXXXXX).\n"
        "2. Click 'Load Items' to see every mod/resource pack/shader in the collection individually, each with "
        "its own checkbox — everything is checked by default. Uncheck anything you don't want (this step is "
        "optional: without it, the download just uses the category filters from step 4).\n"
        "3. Choose the Minecraft version and mod loader. If the version/loader you need isn't in the list yet "
        "(e.g. it was just released), you can simply type it into the field.\n"
        "4. Check what you want to include in the download: Mods/Plugins/Datapacks, Resource/Texture Packs and/or "
        "Shaders (checking/unchecking here also checks/unchecks every item of that category in the individual "
        "list, if it has already been loaded).\n"
        "5. Optionally enable 'Download dependencies' so required dependencies of each mod are downloaded too.\n"
        "6. Choose whether you always want the latest stable (release) version, or the newest available version "
        "even if it's alpha/beta.\n"
        "7. Choose whether you want the files in an organized folder or compressed into a single .zip, and pick "
        "the destination folder.\n"
        "8. Click 'Download Collection' and follow the progress — the 'Cancel' button is available while it runs.\n\n"
        "FOLDER ORGANIZATION\n"
        "The app automatically sorts downloaded files into subfolders based on the type reported by the Modrinth "
        "API and the loader of the downloaded version:\n"
        "  • mods/          -> mods for Fabric, Forge, NeoForge, Quilt, etc.\n"
        "  • resourcepacks/ -> resource packs and texture packs (Modrinth does not officially separate the two)\n"
        "  • shaderpacks/   -> shaders\n"
        "  • plugins/       -> server plugins (Bukkit, Spigot, Paper, Purpur, Folia, Sponge, Velocity, etc.)\n"
        "  • datapacks/     -> datapacks\n\n"
        "RESULTS\n"
        "  • Success: the file was downloaded normally.\n"
        "  • Failed: there was a network/write error while trying to download the file.\n"
        "  • Incompatible: the mod exists, but has no published version for the chosen Minecraft version + loader.\n"
        "  • Skipped: items outside the filters checked in 'Include in download', or manually unchecked in the "
        "items list.\n\n"
        "ABOUT SAFETY\n"
        "This app only queries Modrinth's public API (api.modrinth.com) and downloads the official files hosted "
        "by Modrinth itself (cdn.modrinth.com). No other data is sent, collected, or executed."
    ),
    "btn_close": "Close",
}

STRINGS: Dict[str, Dict[str, str]] = {"pt": _PT, "en": _EN}


def t(lang: str, key: str, **kwargs) -> str:
    """Return the translated text for `lang`, falling back to English and then to the key itself."""
    table = STRINGS.get(lang, _EN)
    text = table.get(key) or _EN.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
