//
//  std_map_db.h
//  YCSB-cpp
//
//  Data-structure adapter backed by std::map.
//
//  In-memory only: records are stored as key -> serialized Fields blob in a
//  single-owner std::map. It implements only the primitive DBInterface
//  contract (core/db_interfaces.h) and is deliberately NOT thread-safe: the
//  runtime drives data-structure adapters with a single instance and a single
//  thread, reusing that instance across the `-load` and `-run` phases of one
//  process. Use the `map.clear` property to start from an empty store on Init.
//

#ifndef YCSB_C_STD_MAP_DB_H_
#define YCSB_C_STD_MAP_DB_H_

#include <map>
#include <string>
#include <vector>

#include "core/db_interfaces.h"
#include "utils/properties.h"

namespace ycsbc {

class StdMapDB : public DBInterface {
 public:
  StdMapDB() {}
  ~StdMapDB() override {}

  void Init() override;

  Status Get(const std::string &table, Slice key, std::string &value) override;

  Status Put(const std::string &table, Slice key, Slice value) override;

  Status Erase(const std::string &table, Slice key) override;

  Status Range(const std::string &table, Slice key, int count,
               std::vector<std::string> &out) override;

  StoreStats GetStats(const std::string &table) override;

 private:
  std::map<std::string, std::string> db_;
};

DBInterface *NewStdMapDB();

}  // namespace ycsbc

#endif  // YCSB_C_STD_MAP_DB_H_
