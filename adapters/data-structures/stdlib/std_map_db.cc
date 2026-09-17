//
//  std_map_db.cc
//  YCSB-cpp
//
//  Data-structure adapter backed by std::map.
//

#include "std_map_db.h"

#include "core/db_factory.h"

namespace {
const std::string PROP_CLEAR = "map.clear";
const std::string PROP_CLEAR_DEFAULT = "false";
}  // namespace

namespace ycsbc {

void StdMapDB::Init() {
  // `map.clear` means "start this instance with an empty store". The runtime
  // keeps one instance across a combined `-load -run` invocation, so the run
  // phase still sees the data the load phase inserted.
  if (props_ != nullptr &&
      props_->GetProperty(PROP_CLEAR, PROP_CLEAR_DEFAULT) == "true") {
    db_.clear();
  }
}

DBInterface::Status StdMapDB::Get(const std::string &table, Slice key,
                                  std::string &value) {
  auto it = db_.find(key.ToString());
  if (it == db_.end()) {
    return kNotFound;
  }
  value = it->second;
  return kOK;
}

DBInterface::Status StdMapDB::Put(const std::string &table, Slice key,
                                  Slice value) {
  db_[key.ToString()].assign(value.data(), value.size());
  return kOK;
}

DBInterface::Status StdMapDB::Erase(const std::string &table, Slice key) {
  return db_.erase(key.ToString()) > 0 ? kOK : kNotFound;
}

DBInterface::Status StdMapDB::Range(const std::string &table, Slice key,
                                    int count, std::vector<std::string> &out) {
  out.clear();
  auto it = db_.lower_bound(key.ToString());
  for (int i = 0; it != db_.end() && i < count; ++it, ++i) {
    out.push_back(it->second);
  }
  return kOK;
}

DBInterface::StoreStats StdMapDB::GetStats(const std::string &table) {
  StoreStats stats;
  stats.current_size = db_.size();
  // Rough std::map footprint estimate: per entry, the rb-tree node carries
  // the value pair plus tree linkage (3 pointers + color byte + padding).
  const uint64_t tree_linkage_bytes = 32;
  const uint64_t entry_bytes = sizeof(std::pair<const std::string, std::string>);
  stats.overhead_bytes = stats.current_size * (entry_bytes + tree_linkage_bytes);
  return stats;
}

DBInterface *NewStdMapDB() { return new StdMapDB; }

const bool registered = DBFactory::RegisterDataStructure("map", NewStdMapDB);

}  // namespace ycsbc
