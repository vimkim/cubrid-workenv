# Show available commands.
default:
    @just --list

alias install := sync

# Install or refresh an independent cub-workenv command for daily-update-cubrid.
sync:
    #!/usr/bin/env bash
    set -euo pipefail
    export UV_TOOL_BIN_DIR="${CUB_WORKENV_BIN_DIR:-$(uv tool dir --bin)}"
    destination="$UV_TOOL_BIN_DIR/cub-workenv"
    install_args=(--reinstall)
    # Allow uv to replace only the legacy symlink installed from this checkout.
    if [[ -L "$destination" && "$(readlink -f -- "$destination")" == "$(realpath -- bin/cub-workenv)" ]]; then
        install_args+=(--force)
    fi
    uv tool install "${install_args[@]}" .
    "$destination" --help >/dev/null
