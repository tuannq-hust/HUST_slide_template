#!/usr/bin/env bash
set -e

# Base dir of this script
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper: convert all PNG in a dir to PDF in parallel
convert_dir() {
  local dir="$1"
  local size="$2"      # e.g. 1920x1080 or 1440x1080

  (
    cd "$dir" || exit 1
    shopt -s nullglob
    echo "Converting in $dir ..."
    for f in *.png; do
      convert "$f" -resize "$size" -density 100 -quality 50 "${f%.png}.pdf" &
    done
    wait
    echo "Done: $dir"
  )
}

# Helper: convert logos 100x smaller (10% size) in parallel
convert_logo_dir() {
  local dir="$1"

  (
    cd "$dir" || exit 1
    shopt -s nullglob
    echo "Converting logos in $dir ..."
    for f in *.png; do
      # 10% in each dimension ≈ 100x fewer pixels
      convert "$f" -resize 10% -density 100 -quality 50 "${f%.png}.pdf" &
    done
    wait
    echo "Done logos: $dir"
  )
}

# Run each group in background (parallel between folders)
convert_dir      "$BASE_DIR/assets/blue_16x9" "1920x1080" &
convert_dir      "$BASE_DIR/assets/red_16x9"  "1920x1080" &
convert_dir      "$BASE_DIR/assets/blue_4x3"  "1440x1080" &
convert_dir      "$BASE_DIR/assets/red_4x3"   "1440x1080" &
convert_logo_dir "$BASE_DIR/assets/logo"      &

# Wait for all background jobs
wait

echo "All conversions finished."
