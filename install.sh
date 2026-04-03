#!/usr/bin/env bash
# OLCLI Installer
set -e

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "  ██████╗ ██╗      ██████╗██╗     ██╗"
echo " ██╔═══██╗██║     ██╔════╝██║     ██║"
echo " ██║   ██║██║     ██║     ██║     ██║"
echo " ██║   ██║██║     ██║     ██║     ██║"
echo " ╚██████╔╝███████╗╚██████╗███████╗██║"
echo "  ╚═════╝ ╚══════╝ ╚═════╝╚══════╝╚═╝"
echo -e "${RESET}"
echo -e "${BOLD}OLCLI Installer${RESET}"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found.${RESET}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "Python version: ${GREEN}${PYTHON_VERSION}${RESET}"

# Check Ollama
if ! command -v ollama &>/dev/null; then
    echo -e "${YELLOW}Warning: Ollama not found. Install from https://ollama.com${RESET}"
else
    echo -e "Ollama: ${GREEN}found${RESET}"
fi

# Install
echo ""
echo -e "${BOLD}Installing OLCLI...${RESET}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pip3 install -e "${SCRIPT_DIR}" --quiet

echo ""
echo -e "${GREEN}${BOLD}✓ OLCLI installed successfully!${RESET}"
echo ""
echo -e "Run ${CYAN}${BOLD}olcli${RESET} to start, or ${CYAN}${BOLD}olcli --help${RESET} for options."
echo ""
echo -e "Quick start:"
echo -e "  ${YELLOW}ollama pull llama3.2${RESET}   # Pull a model"
echo -e "  ${YELLOW}olcli${RESET}                  # Start OLCLI"
