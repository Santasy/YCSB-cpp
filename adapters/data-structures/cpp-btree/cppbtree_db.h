//
//  cppbtree_db.h
//  YCSB-cpp
//
//  Data-structure adapter backed by Google cpp-btree's btree_map.
//
//  In-memory only: records are stored as key -> value string in a single-owner
//  btree::btree_map member. It implements only the primitive DBInterface
//  contract (core/db_interfaces.h) and is deliberately NOT thread-safe: the
//  runtime drives data-structure adapters with a single instance and a single
//  thread, reusing that instance across the `-load` and `-run` phases of one
//  process. Use the `btree.clear` property to start from an empty store on
//  Init. The cpp-btree implementation is header-only (Apache-2.0, submoduled
//  at adapters/data-structures/cpp-btree/module-cpp-btree/).
//

#ifndef YCSB_C_CPPBTREE_DB_H_
#define YCSB_C_CPPBTREE_DB_H_

#include <string>
#include <vector>

#include "btree/btree_map.h"
#include "core/db_interfaces.h"
#include "utils/properties.h"

namespace ycsbc {

class CppBTreeDB : public DBInterface {
  public:
    CppBTreeDB() {}
    ~CppBTreeDB() override {}

    void Init() override;

    Status Get(const std::string &table, Slice key,
               std::string &value) override;

    Status Put(const std::string &table, Slice key, Slice value) override;

    Status Erase(const std::string &table, Slice key) override;

    Status Range(const std::string &table, Slice key, int count,
                 std::vector<std::string> &out) override;

    StoreStats GetStats(const std::string &table) override;

  private:
    btree::btree_map<std::string, std::string> db_;
};

DBInterface *NewCppBTreeDB();

} // namespace ycsbc

#endif // YCSB_C_CPPBTREE_DB_H_