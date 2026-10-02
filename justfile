# Keep the checkout in place: the launcher imports its adjacent Python package.
default:
    @just --list

# Link cub-workenv into an existing user PATH directory without replacing files.
install:
    #!/usr/bin/env bash
    set -euo pipefail
    source_cli="$(realpath -- bin/cub-workenv)"
    install_dir="${CUB_WORKENV_BIN_DIR:-$HOME/.local/bin}"
    mkdir -p -- "$install_dir"
    install_dir="$(realpath -- "$install_dir")"
    destination="$install_dir/cub-workenv"
    if [[ -e "$destination" || -L "$destination" ]]; then
        if [[ ! -L "$destination" || "$(readlink -f -- "$destination")" != "$source_cli" ]]; then
            printf 'Refusing to replace existing path: %s\n' "$destination" >&2
            exit 1
        fi
    else
        ln -s -- "$source_cli" "$destination"
    fi
    "$destination" --help >/dev/null
    printf 'Installed %s -> %s\n' "$destination" "$source_cli"
    if ! command -v cub-workenv >/dev/null 2>&1; then
        printf 'Add this directory to your shell PATH: %s\n' "$install_dir"
        printf 'Bash: export PATH=%q:"$PATH"\n' "$install_dir"
        printf 'Nushell: path add %q\n' "$install_dir"
    elif [[ "$(realpath -- "$(command -v cub-workenv)")" != "$source_cli" ]]; then
        printf 'Another cub-workenv precedes this installation on PATH; put %s first.\n' "$install_dir"
    fi
