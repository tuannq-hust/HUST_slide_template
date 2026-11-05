#!/usr/bin/env bash
# Wrapper to run the PDF cropping script using the built-in job list.
# Usage: ./crop_logos.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/pdf_crop.py" --csv "$SCRIPT_DIR/crop_data.csv" "$@"
