#!/bin/bash

# Build one ycsb executable Wtree target node size, all sharing a single
# CMake binary dir (build-wt-reuse/). Each variant is a single-instantiation binary
# named ycsb-wt-<size> so the node size is unambiguous from the binary name.
#
#CMake recompiles only wtree_db.cc when WTREE_TARGET_NODE_BYTES changes.

set -e

# Resolve the repo root from this script's location so it can be invoked from
# any cwd; the CMake dir (build-wt-reuse/) and collected binaries (build-wt/)
# stay under the repo root.
ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$ROOT_DIR"

BUILD_DIR="${WTREE_BUILD_DIR:-build-wt-reuse}"
WTREE_NODE_SIZES="${WTREE_NODE_SIZES:-256 512 1024 2048 4096 8192 16384}"
BUILD_TYPE="${WTREE_BUILD_TYPE:-Release}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"

COLLECT_DIR="${WTREE_COLLECT_DIR:-build-wt}"
mkdir -p "${COLLECT_DIR}"

for n in $WTREE_NODE_SIZES; do
	echo "=== Building ycsb with WTREE_TARGET_NODE_BYTES=${n} ==="
	cmake -S . -B "$BUILD_DIR" \
		-DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
		-DBIND_WTREE=ON \
		-DWTREE_TARGET_NODE_BYTES="$n"
	cmake --build "$BUILD_DIR" -j"$BUILD_JOBS"
	cp "$BUILD_DIR/ycsb" "$COLLECT_DIR/ycsb-wt-${n}"
done
rm -r "$BUILD_DIR"

echo "=== Built variants ==="
ls -l "$COLLECT_DIR"/ycsb-wt-*
