#!/bin/bash

# Build one ycsb executable per cpp-btree target node size, all sharing a single
# CMake binary dir (build-bt-reuse/). Each variant is a single-instantiation binary
# named ycsb-bt-<size> so the node size is unambiguous from the binary name.
#
#CMake recompiles only cppbtree_db.cc when BTREE_TARGET_NODE_SIZE changes.

set -e

# Resolve the repo root from this script's location so it can be invoked from
# any cwd; the CMake dir (build-bt-reuse/) and collected binaries (build-bt/)
# stay under the repo root.
ROOT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$ROOT_DIR"

BUILD_DIR="${BTREE_BUILD_DIR:-build-bt-reuse}"
BTREE_NODE_SIZES="${BTREE_NODE_SIZES:-256 512 1024 2048 4096 8192 16384}"
BUILD_TYPE="${BTREE_BUILD_TYPE:-Release}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"

COLLECT_DIR="${BTREE_COLLECT_DIR:-build-bt}"
mkdir -p "${COLLECT_DIR}"

for n in $BTREE_NODE_SIZES; do
	echo "=== Building ycsb with BTREE_TARGET_NODE_SIZE=${n} ==="
	cmake -S . -B "$BUILD_DIR" \
		-DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
		-DBIND_BTREE=ON \
		-DBTREE_TARGET_NODE_SIZE="$n"
	cmake --build "$BUILD_DIR" -j"$BUILD_JOBS"
	cp "$BUILD_DIR/ycsb" "$COLLECT_DIR/ycsb-bt-${n}"
done
rm -r "$BUILD_DIR"

echo "=== Built variants ==="
ls -l "$COLLECT_DIR"/ycsb-bt-*
