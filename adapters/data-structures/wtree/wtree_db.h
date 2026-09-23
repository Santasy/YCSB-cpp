//
//  wtree_db.h
//  YCSB-cpp
//
//  Data-structure adapter backed by WTree's WTreeLib::map.
//
//  In-memory only: records are stored as key -> value string in a single-owner
//  WTreeLib::map member. It implements only the primitive DBInterface
//  contract (core/db_interfaces.h) and is deliberately NOT thread-safe: the
//  runtime drives data-structure adapters with a single instance and a single
//  thread, reusing that instance across the `-load` and `-run` phases of one
//  process. Use the `wtree.clear` property to start from an empty store on
//  Init. The WTree implementation is header-only (Apache-2.0, submoduled at
//  adapters/data-structures/wtree/module-wtree/).
//

#ifndef YCSB_C_WTREE_DB_H_
#define YCSB_C_WTREE_DB_H_

#include <functional>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "core/db_interfaces.h"
#include "utils/properties.h"
#include "wtree/map.hpp"

// Target bytes per WTree node, fixed at compile time so each built executable
// contains a single WTreeLib::map instantiation (the node size sets the
// branch/target fanout k). Override per build (CMake cache var
// WTREE_TARGET_NODE_BYTES / -D) to sweep node sizes across binaries, mirroring
// BTREE_TARGET_NODE_SIZE for cpp-btree.
#ifndef WTREE_TARGET_NODE_BYTES
#define WTREE_TARGET_NODE_BYTES 512
#endif

namespace ycsbc {

using WTreeMap =
    WTreeLib::map<std::string, std::string, std::less<std::string>,
                  std::allocator<std::pair<const std::string, std::string>>,
                  WTREE_TARGET_NODE_BYTES>;

class WTreeDB : public DBInterface {
  public:
    WTreeDB() {}
    ~WTreeDB() override {}

    void Init() override;

    Status Get(const std::string &table, Slice key,
               std::string &value) override;

    Status Put(const std::string &table, Slice key, Slice value) override;

    Status Erase(const std::string &table, Slice key) override;

    Status Range(const std::string &table, Slice key, int count,
                 std::vector<std::string> &out) override;

    StoreStats GetStats(const std::string &table) override;

  private:
    WTreeMap db_;
};

DBInterface *NewWTreeDB();

} // namespace ycsbc

#endif // YCSB_C_WTREE_DB_H_