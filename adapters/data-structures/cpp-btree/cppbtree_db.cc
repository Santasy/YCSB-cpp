//
//  cppbtree_db.cc
//  YCSB-cpp
//
//  Data-structure adapter backed by btree::btree_map.
//

#include "cppbtree_db.h"

#include "core/db_factory.h"

namespace {
const std::string PROP_CLEAR = "btree.clear";
const std::string PROP_CLEAR_DEFAULT = "false";
} // namespace

namespace ycsbc {

void CppBTreeDB::Init() {
    // `btree.clear` means "start this instance with an empty store". The
    // runtime keeps one instance across a combined `-load -run` invocation, so
    // the run phase still sees the data the load phase inserted.
    if(props_ != nullptr &&
       props_->GetProperty(PROP_CLEAR, PROP_CLEAR_DEFAULT) == "true") {
        db_.clear();
    }
}

DBInterface::Status CppBTreeDB::Get(const std::string &table, Slice key,
                                    std::string &value) {
    auto it = db_.find(key.ToString());
    if(it == db_.end()) {
        return kNotFound;
    }
    value = it->second;
    return kOK;
}

DBInterface::Status CppBTreeDB::Put(const std::string &table, Slice key,
                                    Slice value) {
    db_[key.ToString()].assign(value.data(), value.size());
    return kOK;
}

DBInterface::Status CppBTreeDB::Erase(const std::string &table, Slice key) {
    return db_.erase(key.ToString()) > 0 ? kOK : kNotFound;
}

DBInterface::Status CppBTreeDB::Range(const std::string &table, Slice key,
                                      int count,
                                      std::vector<std::string> &out) {
    out.clear();
    auto it = db_.lower_bound(key.ToString());
    for(int i = 0; it != db_.end() && i < count; ++it, ++i) {
        out.push_back(it->second);
    }
    return kOK;
}

DBInterface::StoreStats CppBTreeDB::GetStats(const std::string &table) {
    StoreStats stats;
    stats.current_size = db_.size();
    // cpp-btree reports its own actual node footprint directly; taller/less
    // full trees cost more bytes, unlike std::map's flat per-entry estimate.
    stats.overhead_bytes =
        db_.bytes_used() - (stats.current_size *
                            sizeof(std::pair<const std::string, std::string>));
    // Structure-specific metrics land in the container's schema.csv as extra
    // columns (height, leaf/internal node counts).
    stats.extra.emplace_back("btree_height", std::to_string(db_.height()));
    stats.extra.emplace_back("btree_leaf_nodes",
                             std::to_string(db_.leaf_nodes()));
    stats.extra.emplace_back("btree_internal_nodes",
                             std::to_string(db_.internal_nodes()));
    return stats;
}

DBInterface *NewCppBTreeDB() { return new CppBTreeDB; }

const bool registered =
    DBFactory::RegisterDataStructure("btree", NewCppBTreeDB);

} // namespace ycsbc