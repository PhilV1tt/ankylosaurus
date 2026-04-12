#!/usr/bin/env bash
set -euo pipefail

# ANKYLOSAURUS bootstrap — works on machines with or without Python
# Usage: curl -fsSL https://raw.githubusercontent.com/PhilV1tt/ankylosaurus/main/bootstrap.sh | bash

REPO="https://github.com/PhilV1tt/ankylosaurus.git"
INSTALL_DIR="$HOME/.ankylosaurus/app"
MIN_PYTHON="3.10"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${GREEN}[+]${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}[!]${RESET} %s\n" "$1"; }
fail()  { printf "${RED}[x]${RESET} %s\n" "$1"; exit 1; }

# --- Detect OS ---
detect_os() {
    case "$(uname -s)" in
        Darwin*)  echo "macos" ;;
        Linux*)   echo "linux" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

# --- Check if command exists ---
has() { command -v "$1" &>/dev/null; }

# --- Check Python version >= MIN_PYTHON ---
python_ok() {
    local py="$1"
    $py -c "
import sys
v = sys.version_info
exit(0 if (v.major, v.minor) >= (${MIN_PYTHON//./, }) else 1)
" 2>/dev/null
}

# --- Find a working Python ---
find_python() {
    for cmd in python3 python python3.13 python3.12 python3.11 python3.10; do
        if has "$cmd" && python_ok "$cmd"; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

# --- Install Python if missing ---
install_python() {
    local os="$1"
    warn "Python >= $MIN_PYTHON not found. Installing..."

    case "$os" in
        macos)
            if has brew; then
                info "Installing Python via Homebrew..."
                brew install python@3.12
            else
                info "Installing Homebrew first..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                # Add brew to PATH for this session
                if [ -f /opt/homebrew/bin/brew ]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                elif [ -f /usr/local/bin/brew ]; then
                    eval "$(/usr/local/bin/brew shellenv)"
                fi
                brew install python@3.12
            fi
            ;;
        linux)
            if has apt-get; then
                info "Installing Python via apt..."
                sudo apt-get update -qq
                sudo apt-get install -y -qq python3 python3-venv python3-pip
            elif has dnf; then
                info "Installing Python via dnf..."
                sudo dnf install -y python3 python3-pip
            elif has pacman; then
                info "Installing Python via pacman..."
                sudo pacman -Sy --noconfirm python python-pip
            elif has zypper; then
                info "Installing Python via zypper..."
                sudo zypper install -y python3 python3-pip
            else
                fail "No supported package manager found (apt/dnf/pacman/zypper). Install Python >= $MIN_PYTHON manually."
            fi
            ;;
        windows)
            if has winget; then
                info "Installing Python via winget..."
                winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            else
                fail "Install Python >= $MIN_PYTHON from https://python.org and re-run this script."
            fi
            ;;
        *)
            fail "Unsupported OS. Install Python >= $MIN_PYTHON manually."
            ;;
    esac
}

# --- Install git if missing ---
install_git() {
    local os="$1"
    warn "git not found. Installing..."

    case "$os" in
        macos)
            if has brew; then
                brew install git
            else
                # xcode command line tools include git
                xcode-select --install 2>/dev/null || true
                info "Accept the Xcode Command Line Tools prompt, then re-run this script."
                exit 0
            fi
            ;;
        linux)
            if has apt-get; then
                sudo apt-get update -qq && sudo apt-get install -y -qq git
            elif has dnf; then
                sudo dnf install -y git
            elif has pacman; then
                sudo pacman -Sy --noconfirm git
            else
                fail "Install git manually and re-run."
            fi
            ;;
        *)
            fail "Install git manually and re-run."
            ;;
    esac
}

# ============================================================
# Main
# ============================================================

printf "\n${BOLD}ANKYLOSAURUS -- local-llm-setup bootstrap${RESET}\n\n"

OS=$(detect_os)
info "Detected OS: $OS"

# 1. Ensure git
if ! has git; then
    install_git "$OS"
fi

# 2. Ensure Python
if ! find_python &>/dev/null; then
    install_python "$OS"
fi

PYTHON=$(find_python) || fail "Python >= $MIN_PYTHON still not found after install attempt."
info "Using: $PYTHON ($($PYTHON --version))"

# 3. Clone or update repo
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
    git -C "$INSTALL_DIR" pull --quiet
else
    info "Downloading ANKYLOSAURUS..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 --quiet "$REPO" "$INSTALL_DIR"
fi

# 4. Create venv and install deps
info "Setting up Python environment..."
$PYTHON -m venv "$INSTALL_DIR/.venv"

# Activate
if [ "$OS" = "windows" ]; then
    source "$INSTALL_DIR/.venv/Scripts/activate"
else
    source "$INSTALL_DIR/.venv/bin/activate"
fi

pip install --upgrade pip --quiet 2>/dev/null
pip install "$INSTALL_DIR" --quiet 2>/dev/null

# 5. Create launcher wrapper
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

VENV_BIN="$INSTALL_DIR/.venv/bin"
if [ "$OS" = "windows" ]; then
    VENV_BIN="$INSTALL_DIR/.venv/Scripts"
fi

cat > "$BIN_DIR/ankylosaurus" << LAUNCHER
#!/usr/bin/env bash
exec "$VENV_BIN/ankylosaurus" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/ankylosaurus"

# 6. Ensure ~/.local/bin is in PATH
add_to_path() {
    local rc="\$1"
    if [ -f "\$rc" ] && grep -q '.local/bin' "\$rc" 2>/dev/null; then
        return
    fi
    if [ -f "\$rc" ] || [ "\$rc" = "\$HOME/.zshrc" ] || [ "\$rc" = "\$HOME/.bashrc" ]; then
        printf '\n# ANKYLOSAURUS\nexport PATH="\$HOME/.local/bin:\$PATH"\n' >> "\$rc"
    fi
}

case "$OS" in
    macos)  add_to_path "$HOME/.zshrc" ;;
    linux)
        if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
            add_to_path "$HOME/.zshrc"
        else
            add_to_path "$HOME/.bashrc"
        fi
        ;;
esac

export PATH="$BIN_DIR:$PATH"

# 7. Done
printf "\n${GREEN}${BOLD}ANKYLOSAURUS installed.${RESET}\n\n"
printf "  Run now:          ${BOLD}ankylosaurus install${RESET}\n"
printf "  Or full path:     ${BOLD}%s/ankylosaurus install${RESET}\n" "$BIN_DIR"
printf "\n  If 'ankylosaurus' is not found, restart your terminal or run:\n"
printf "    export PATH=\"\$HOME/.local/bin:\$PATH\"\n\n"
