# Copyright 2023 Chengye YU <yuchengye2013 AT outlook.com>.
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.12)
project(ycsb-cpp LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Enable verbose compilation output
set(CMAKE_VERBOSE_MAKEFILE OFF)

# Set general optimization level to -O3 for GCC only in Release mode
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic -g")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Wpedantic -g")
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3")
        set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3")
    endif()
endif()

# set(CMAKE_BUILD_TYPE Release)
set(CompilerFlags
        CMAKE_CXX_FLAGS
        CMAKE_CXX_FLAGS_DEBUG
        CMAKE_CXX_FLAGS_RELEASE
        CMAKE_C_FLAGS
        CMAKE_C_FLAGS_DEBUG
        CMAKE_C_FLAGS_RELEASE
        )

if(MSVC)
    foreach(CompilerFlag ${CompilerFlags})
        string(REPLACE "/MD" "/MT" ${CompilerFlag} "${${CompilerFlag}}")
    endforeach()
endif()

### Data Bases ###
option(BIND_ROCKSDB "build with rocksdb" OFF)
option(BIND_LMDB "build with lmdb" OFF)
option(BIND_LEVELDB "build with leveldb" OFF)
option(BIND_WIREDTIGER "build with wiredtiger" OFF)
option(BIND_LEAVES "build with leaves" OFF)
option(BIND_SQLITE "build with sqlite" OFF)
option(BIND_REDIS "build with redis" OFF)
option(BIND_AEROSPIKE "build with aerospike" OFF)

option(WITH_ZLIB "link with zlib (only used by HdrHistogram's optional log compression); safe to leave OFF" ON)
option(WITH_LZ4 "linking YCSB with lz4" OFF)
option(WITH_SNAPPY "linking YCSB with snappy" OFF)
option(WITH_ZSTD "linking YCSB with zstd" OFF)
option(WITH_BZ2 "linking YCSB with bzip2" OFF)

### Data Structures ###
option(BIND_BTREE "linking YCSB with cpp-btree" OFF)
set(BTREE_TARGET_NODE_SIZE 256 CACHE STRING
    "cpp-btree TargetNodeSize (bytes) compiled into this build; one value per binary")
    
option(BIND_WTREE "linking YCSB with WTree" OFF)
set(WTREE_TARGET_NODE_BYTES 512 CACHE STRING
    "WTree target node bytes compiled into this build; one value per binary")

### Test ###
option(YCSB_BUILD_TESTS "build the optional test executables" OFF)

file(GLOB_RECURSE YCSB_CORE_SRC CONFIGURE_DEPENDS "core/*.cc")
file(GLOB_RECURSE YCSB_NULL_SRC CONFIGURE_DEPENDS "adapters/null/*.cc")

include(FindThreads)

# --- Core bindings -------------------------------------------------
# ycsb_core: OBJECT target holding the core/*.cc sources. Compiled once and
# linked into both ycsb and ycsb_tests so symbols whose key function lives in a
# core TU (e.g. DBInterface's vtable/typeinfo in core/db_interfaces.cc) are
# available to both executables.
# core/ycsbc.cc defines main() and is therefore
# kept out of the library and compiled only into the ycsb executable.
set(YCSB_MAIN_SRC ${CMAKE_CURRENT_SOURCE_DIR}/core/ycsbc.cc)
list(FILTER YCSB_CORE_SRC EXCLUDE REGEX "(^|/)ycsbc\\.cc$")
add_library(ycsb_core OBJECT ${YCSB_CORE_SRC} ${CMAKE_CURRENT_SOURCE_DIR}/utils/sha256.cpp)
target_include_directories(ycsb_core PUBLIC ${PROJECT_SOURCE_DIR})

# --- Data-structure bindings -------------------------------------------------
# ycsb_data_structs: OBJECT target holding all data-structure adapter sources
# (e.g. std::map / std::set). They have no external deps, so they are always
# compiled (the "map" backend is in-memory only). stdlib is globbed
# recursively; cpp-btree and WTree are opt-in via BIND_BTREE / BIND_WTREE and
# globbed only at the top level so each module subdir's own (test) sources are
# not pulled in.
file(GLOB_RECURSE YCSB_STDMAP_SRC CONFIGURE_DEPENDS "adapters/data-structures/stdlib/*.cc")
add_library(ycsb_data_structs OBJECT ${YCSB_STDMAP_SRC})
target_include_directories(ycsb_data_structs PUBLIC ${PROJECT_SOURCE_DIR})

if (BIND_BTREE)
    message(STATUS "BIND_BTREE - ON")
    # cpp-btree is a header-only library under its submodule include root.
    target_include_directories(ycsb_data_structs PUBLIC
        ${PROJECT_SOURCE_DIR}/adapters/data-structures/cpp-btree/module-cpp-btree/include)
    file(GLOB YCSB_BTREE_SRC CONFIGURE_DEPENDS "adapters/data-structures/cpp-btree/*.cc")
    target_sources(ycsb_data_structs PRIVATE ${YCSB_BTREE_SRC})
    # Scope the node-size define to the btree TU only, so reconfiguring with a new
    # value rebuilds just this source (template instantiation) instead of the whole tree.
    set_source_files_properties(${YCSB_BTREE_SRC}
        PROPERTIES COMPILE_DEFINITIONS "BTREE_TARGET_NODE_SIZE=${BTREE_TARGET_NODE_SIZE}")
    if(NOT MSVC)
        # The (old, 2013-era) cpp-btree headers trigger -Wdeprecated-copy under
        # C++20/-Wextra; keep the build output clean without -Werror.
        set_source_files_properties(${YCSB_BTREE_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter;-Wno-deprecated-copy;-Wno-array-bounds")
    endif()
endif()

if (BIND_WTREE)
    message(STATUS "BIND_WTREE - ON")
    # WTree is a header-only library under its submodule include root.
    target_include_directories(ycsb_data_structs PUBLIC
        ${PROJECT_SOURCE_DIR}/adapters/data-structures/wtree/module-wtree/include)
    file(GLOB YCSB_WTREE_SRC CONFIGURE_DEPENDS "adapters/data-structures/wtree/*.cc")
    target_sources(ycsb_data_structs PRIVATE ${YCSB_WTREE_SRC})
    # Scope the node-size define to the wtree TU only, so reconfiguring with a new
    # value rebuilds just this source (template instantiation) instead of the whole tree.
    set_source_files_properties(${YCSB_WTREE_SRC}
        PROPERTIES COMPILE_DEFINITIONS "WTREE_TARGET_NODE_BYTES=${WTREE_TARGET_NODE_BYTES}")
    if(NOT MSVC)
        # The WTree node/get-stats headers trip GCC's -Warray-bounds /
        # -Wstringop-overflow / -Wmaybe-uninitialized forensics on the flexible
        # array layout (the latter two are GCC-only); keep the build output
        # clean without -Werror.
        set(WTREE_COMPILE_OPTIONS "-Wno-unused-parameter;-Wno-array-bounds")
        if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
            list(APPEND WTREE_COMPILE_OPTIONS
                 "-Wno-stringop-overflow;-Wno-maybe-uninitialized")
        endif()
        set_source_files_properties(${YCSB_WTREE_SRC}
            PROPERTIES COMPILE_OPTIONS "${WTREE_COMPILE_OPTIONS}")
    endif()
endif()

# --- Database adaptors --------------------------------------------------------
# ycsb_db_adaptors: OBJECT target holding all database adapter sources. OBJECT
# libraries keep the adapters' static self-registration intact and let the
# PUBLIC usage requirements (includes, linked libs) propagate to ycsb.
# The null binding (adapters/null -> NullDB, the "basic" DB) is always
# compiled: it has no external deps and keeps ycsb runnable with -db basic.
# Every other adapter adds itself below inside its own if(BIND_*) block, so
# builds stay compatible with all DBs while never pulling in uninstalled
# headers.
add_library(ycsb_db_adaptors OBJECT adapters/null/null_db.cc)

if(NOT MSVC)
    set_source_files_properties(${YCSB_CORE_SRC} ${YCSB_MAIN_SRC} ${YCSB_NULL_SRC} ${YCSB_STDMAP_SRC}
        PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter")
endif()
target_include_directories(ycsb_db_adaptors PUBLIC ${PROJECT_SOURCE_DIR})

if (BIND_ROCKSDB)
    message(STATUS "BIND_ROCKSDB - ON")
    set(WITH_ZLIB ON)
    set(WITH_BZ2 ON)
    file(GLOB_RECURSE YCSB_ROCKSDB_SRC "adapters/data-bases/rocksdb/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_ROCKSDB_SRC})
    if(NOT MSVC)
        set_source_files_properties(${YCSB_ROCKSDB_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter")
    endif()

    find_package(RocksDB CONFIG)
    if(RocksDB_FOUND)
        if(MSVC)
            target_link_libraries(ycsb_db_adaptors PUBLIC RocksDB::rocksdb rpcrt4.lib)
        else()
            target_link_libraries(ycsb_db_adaptors PUBLIC RocksDB::rocksdb)
        endif()
    else()
        message(STATUS "Try to find rocksdb library using find_library")
        find_library(ROCKSDB_LIB rocksdb REQUIRED)
        find_path(ROCKSDB_INCLUDE_DIR "rocksdb/db.h" REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${ROCKSDB_LIB})
        target_include_directories(ycsb_db_adaptors PUBLIC ${ROCKSDB_INCLUDE_DIR})
    endif()
    message(STATUS "Found RocksDB library")
    if(NOT MSVC)
        target_link_libraries(ycsb_db_adaptors PUBLIC dl)
    endif()
else()
    message(STATUS "BIND_ROCKSDB - OFF")
endif()

if (BIND_LMDB)
    message(STATUS "BIND_LMDB - ON")
    file(GLOB_RECURSE YCSB_LMDB_SRC "adapters/data-bases/lmdb/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_LMDB_SRC})
    if(NOT MSVC)
        set_source_files_properties(${YCSB_LMDB_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter;-Wno-type-limits")
    endif()

    find_package(lmdb CONFIG)
    if(lmdb_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC lmdb)
    else()
        message(STATUS "Try to find lmdb library using find_library")
        find_library(LMDB_LIB lmdb REQUIRED)
        find_path(LMDB_INCLUDE_DIR "lmdb.h" REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${LMDB_LIB})
        target_include_directories(ycsb_db_adaptors PUBLIC ${LMDB_INCLUDE_DIR})
    endif()
    message(STATUS "Found LMDB library")
else()
    message(STATUS "BIND_LMDB - OFF")
endif()

if (BIND_LEVELDB)
    message(STATUS "BIND_LEVELDB - ON")
    file(GLOB_RECURSE YCSB_LEVELDB_SRC "adapters/data-bases/leveldb/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_LEVELDB_SRC})
    if(NOT MSVC)
        set_source_files_properties(${YCSB_LEVELDB_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter")
    endif()

    find_package(leveldb CONFIG)
    if(leveldb_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC leveldb::leveldb)
    else()
        message(STATUS "Try to find leveldb library using find_library")
        find_library(LEVELDB_LIB leveldb REQUIRED)
        find_path(LEVELDB_INCLUDE_DIR "leveldb/db.h" REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${LEVELDB_LIB})
        target_include_directories(ycsb_db_adaptors PUBLIC ${LEVELDB_INCLUDE_DIR})
    endif()
    message(STATUS "Found LevelDB library")
else()
    message(STATUS "BIND_LEVELDB - OFF")
endif()

if (BIND_WIREDTIGER)
    message(STATUS "BIND_WIREDTIGER - ON")
    file(GLOB_RECURSE YCSB_WT_SRC "adapters/data-bases/wiredtiger/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_WT_SRC})
    if(NOT MSVC)
        set_source_files_properties(${YCSB_WT_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter;-Wno-missing-field-initializers")
    endif()

    find_library(WIREDTIGER_LIB wiredtiger REQUIRED)
    find_path(WIREDTIGER_INCLUDE_DIR "wiredtiger.h" REQUIRED)
    target_link_libraries(ycsb_db_adaptors PUBLIC ${WIREDTIGER_LIB})
    target_include_directories(ycsb_db_adaptors PUBLIC ${WIREDTIGER_INCLUDE_DIR})
    message(STATUS "Found WiredTiger library")
else()
    message(STATUS "BIND_WIREDTIGER - OFF")
endif()

if (BIND_LEAVES)
    message(STATUS "BIND_LEAVES - ON")
    file(GLOB_RECURSE YCSB_LEAVES_SRC "adapters/data-bases/leaves/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_LEAVES_SRC})

    # Use only generic package discovery (find_package CONFIG). No hardcoded
    # machine paths: if the Leaves package export is not available, this is a
    # fatal error rather than a silent local-include fallback.
    find_package(leaves CONFIG REQUIRED)
    target_link_libraries(ycsb_db_adaptors PUBLIC leaves::leaves)
    message(STATUS "Found Leaves package target")

    # Suppress pedantic and unused-parameter warnings for leaves headers/adapter
    if(NOT MSVC)
        set_source_files_properties(${YCSB_LEAVES_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-pedantic;-Wno-unused-parameter")
    endif()

    # Add specific compiler optimizations for Leaves files with GCC only in Release mode
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_BUILD_TYPE STREQUAL "Release")
        foreach(LEAVES_FILE ${YCSB_LEAVES_SRC})
            set_source_files_properties(${LEAVES_FILE} PROPERTIES
                COMPILE_FLAGS "-DNDEBUG -DLEAVES_SINGLE_PROCESS -g -march=native -O3 -funroll-loops -flto=auto"
            )
        endforeach()
        message(STATUS "Applied GCC optimizations to Leaves files: -DNDEBUG -DLEAVES_SINGLE_PROCESS -g -march=native -O3 -funroll-loops -flto=auto")
    endif()

    # Add LEAVES_SINGLE_PROCESS for Leaves files in Debug mode
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        foreach(LEAVES_FILE ${YCSB_LEAVES_SRC})
            set_source_files_properties(${LEAVES_FILE} PROPERTIES
                COMPILE_FLAGS "-DLEAVES_SINGLE_PROCESS -g -O0"
            )
        endforeach()
        message(STATUS "Applied Debug flags to Leaves files: -DLEAVES_SINGLE_PROCESS -g -O0")
    endif()
else()
    message(STATUS "BIND_LEAVES - OFF")
endif()

if (BIND_SQLITE)
    message(STATUS "BIND_SQLITE - ON")
    file(GLOB_RECURSE YCSB_SQLITE_SRC "adapters/data-bases/sqlite/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_SQLITE_SRC})
    if(NOT MSVC)
        set_source_files_properties(${YCSB_SQLITE_SRC}
            PROPERTIES COMPILE_OPTIONS "-Wno-unused-parameter;-Wno-unused-variable")
    endif()

    find_package(SQLite3)
    if(SQLite3_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC SQLite::SQLite3)
        target_include_directories(ycsb_db_adaptors PUBLIC ${SQLite3_INCLUDE_DIRS})
    else()
        message(STATUS "Try to find sqlite3 library using find_library")
        find_library(SQLITE3_LIB sqlite3 REQUIRED)
        find_path(SQLITE3_INCLUDE_DIR "sqlite3.h" REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${SQLITE3_LIB})
        target_include_directories(ycsb_db_adaptors PUBLIC ${SQLITE3_INCLUDE_DIR})
    endif()
    message(STATUS "Found SQLite3 library")
else()
    message(STATUS "BIND_SQLITE - OFF")
endif()

if (BIND_REDIS)
    message(STATUS "BIND_REDIS - ON")
    file(GLOB_RECURSE YCSB_REDIS_SRC "adapters/data-bases/redis/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_REDIS_SRC})

    find_library(HIREDIS_LIB hiredis REQUIRED)
    find_path(HIREDIS_INCLUDE_DIR "hiredis/hiredis.h" REQUIRED)
    target_link_libraries(ycsb_db_adaptors PUBLIC ${HIREDIS_LIB})
    target_include_directories(ycsb_db_adaptors PUBLIC ${HIREDIS_INCLUDE_DIR})
    message(STATUS "Found hiredis library")
else()
    message(STATUS "BIND_REDIS - OFF")
endif()

if (BIND_AEROSPIKE)
    message(STATUS "BIND_AEROSPIKE - ON")
    file(GLOB_RECURSE YCSB_AEROSPIKE_SRC "adapters/data-bases/aerospike/*.cc")
    target_sources(ycsb_db_adaptors PRIVATE ${YCSB_AEROSPIKE_SRC})

    find_library(AEROSPIKE_LIB aerospike REQUIRED)
    find_path(AEROSPIKE_INCLUDE_DIR "aerospike/aerospike.h" REQUIRED)
    target_link_libraries(ycsb_db_adaptors PUBLIC ${AEROSPIKE_LIB})
    target_include_directories(ycsb_db_adaptors PUBLIC ${AEROSPIKE_INCLUDE_DIR})
    # Aerospike requires pthread, ssl, crypto, yaml, and libuv for async support
    target_link_libraries(ycsb_db_adaptors PUBLIC pthread ssl crypto yaml uv)
    message(STATUS "Found Aerospike library")
else()
    message(STATUS "BIND_AEROSPIKE - OFF")
endif()

if(WITH_ZLIB)
    message(STATUS "WITH_ZLIB - ON")
    find_package(ZLIB)
    if(ZLIB_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC ZLIB::ZLIB)
    else()
        message(STATUS "Try to find zlib library using find_library")
        find_library(ZLIB_LIB zlib)
        if(ZLIB_LIB)
            target_link_libraries(ycsb_db_adaptors PUBLIC ${ZLIB_LIB})
            message(STATUS "Found zlib library via find_library")
        else()
            message(WARNING
                "WITH_ZLIB requested but zlib not found; "
                "only HdrHistogram's optional log compression (unused by ycsb) "
                "and the RocksDB zlib codec need it, continuing without zlib")
        endif()
    endif()
else()
    message(STATUS "WITH_ZLIB - OFF")
endif()

if(WITH_SNAPPY)
    message(STATUS "WITH_SNAPPY - ON")
    find_package(Snappy CONFIG)
    if(Snappy_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC Snappy::snappy)
    else()
        message(STATUS "Try to find Snappy library using find_library")
        find_library(SNAPPY_LIB snappy REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${SNAPPY_LIB})
    endif()
    message(STATUS "Found Snappy library")
else()
    message(STATUS "WITH_SNAPPY - OFF")
endif()

if(WITH_LZ4)
    message(STATUS "WITH_LZ4 - ON")
    find_package(lz4 CONFIG)
    if(lz4_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC lz4::lz4)
    else()
        message(STATUS "Try to find LZ4 library using find_library")
        find_library(LZ4_LIB lz4 REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${LZ4_LIB})
    endif()
    message(STATUS "Found LZ4 library")
else()
    message(STATUS "WITH_LZ4 - OFF")
endif()

if(WITH_ZSTD)
    message(STATUS "WITH_ZSTD - ON")
    find_package(zstd CONFIG)
    if(zstd_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC $<IF:$<TARGET_EXISTS:zstd::libzstd_shared>,zstd::libzstd_shared,zstd::libzstd_static>)
    else()
        message(STATUS "Try to find zstd library using find_library")
        find_library(ZSTD_LIB zstd REQUIRED)
        target_link_libraries(ycsb_db_adaptors PUBLIC ${ZSTD_LIB})
    endif()
    message(STATUS "Found zstd library")
else()
    message(STATUS "WITH_ZSTD - OFF")
endif()

if(WITH_BZ2)
    message(STATUS "WITH_BZ2 - ON")
    find_package(BZip2)
    if(BZip2_FOUND)
        target_link_libraries(ycsb_db_adaptors PUBLIC BZip2::BZip2)
    else()
        message(STATUS "Try to find BZip2 library using find_library")
        find_library(BZ2_LIB bz2 REQUIRED)
    target_link_libraries(ycsb_db_adaptors PRIVATE ${BZ2_LIB})
endif()
    message(STATUS "Found BZip2 library")
else()
    message(STATUS "WITH_BZ2 - OFF")
endif()



### Grouping Executables ###

add_executable(ycsb ${YCSB_MAIN_SRC})
target_link_libraries(ycsb PRIVATE ycsb_core ycsb_db_adaptors ycsb_data_structs)

if(YCSB_BUILD_TESTS)
    add_executable(ycsb_tests tests/test_fields.cc)
    target_link_libraries(ycsb_tests PRIVATE ycsb_core ycsb_db_adaptors ycsb_data_structs)
endif()
