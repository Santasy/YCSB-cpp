#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"

if [[ $# -gt 2 ]]; then
    printf 'usage: %s [input_dir] [output_file]\n' "$0" >&2
    exit 2
fi

if [[ $# -ge 1 ]]; then
    INPUT_DIR="$1"
else
    INPUT_DIR="${COLLECT_INPUT_DIR:-$ROOT_DIR/storage/logen}"
    if [[ ! -d "$INPUT_DIR" ]]; then
        for candidate in "$ROOT_DIR"/storage/load_order_sweep*; do
            if [[ -d "$candidate" ]]; then
                INPUT_DIR="$candidate"
                break
            fi
        done
    fi
fi

if [[ $# -ge 2 ]]; then
    OUTPUT_FILE="$2"
else
    OUTPUT_FILE="${COLLECT_OUTPUT_FILE:-$INPUT_DIR/all_averages.csv}"
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    printf 'input directory not found: %s\n' "$INPUT_DIR" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

python3 "$ROOT_DIR/scripts/collect_all.py" "$INPUT_DIR" "$OUTPUT_FILE"
