//
//  wtree_db.cc
//  YCSB-cpp
//
//  Data-structure adapter backed by WTreeLib::map.
//

#include "wtree_db.h"

#include <type_traits>

#include "core/db_factory.h"
#include "core/db_interfaces.h"
#include "wtree/optional/profile.hpp"

namespace {
const std::string PROP_CLEAR = "wtree.clear";
const std::string PROP_CLEAR_DEFAULT = "false";
} // namespace

namespace ycsbc {

void WTreeDB::Init() {
    // `wtree.clear` means "start this instance with an empty store". The
    // runtime keeps one instance across a combined `-load -run` invocation, so
    // the run phase still sees the data the load phase inserted.
    if(props_ != nullptr &&
       props_->GetProperty(PROP_CLEAR, PROP_CLEAR_DEFAULT) == "true") {
        db_.clear();
    }
}

DBInterface::Status WTreeDB::Get(const std::string &table, Slice key,
                                 std::string &value) {
    auto it = db_.find(key.ToString());
    if(it == db_.end()) {
        return kNotFound;
    }
    value = it->second;
    return kOK;
}

DBInterface::Status WTreeDB::Put(const std::string &table, Slice key,
                                 Slice value) {
    db_[key.ToString()].assign(value.data(), value.size());
    return kOK;
}

DBInterface::Status WTreeDB::Erase(const std::string &table, Slice key) {
    return db_.erase(key.ToString()) > 0 ? kOK : kNotFound;
}

DBInterface::Status WTreeDB::Range(const std::string &table, Slice key,
                                   int count, std::vector<std::string> &out) {
    out.clear();
    auto it = db_.lower_bound(key.ToString());
    for(int i = 0; it != db_.end() && i < count; ++it, ++i) {
        out.push_back(it->second);
    }
    return kOK;
}

DBInterface::StoreStats WTreeDB::GetStats(const std::string &table) {
    StoreStats stats;
    stats.current_size = db_.size();
    // WTree exposes no O(1) tree-metric accessors yet (containers.hpp only
    // declares fullness()/overhead() stubs), so walk the tree once with the
    // library's profiler. total_bytes is the node footprint beyond the stored
    // key/value strings (node base fields + unused key cells + pointer cells).

    auto wtstats = db_.collect_stats();

    stats.overhead_bytes = wtstats.total_overhead();
    // Structure-specific metrics land in the container's schema.csv as extra
    // columns (height, leaf/internal node counts), mirroring the btree adapter.
    stats.extra.emplace_back("wtree_height", std::to_string(wtstats.height));
    stats.extra.emplace_back("wtree_leaf_nodes",
                             std::to_string(wtstats.leaf_nodes));
    stats.extra.emplace_back("wtree_internal_nodes",
                             std::to_string(wtstats.internal_nodes));
    stats.extra.emplace_back("wtree_fullness",
                             std::to_string(wtstats.fullness()));
    stats.extra.emplace_back("wtree_occupancy",
                             std::to_string(wtstats.occupancy()));
    return stats;
}

DBInterface *NewWTreeDB() {
    return reinterpret_cast<DBInterface *>(new WTreeDB);
}

const bool registered = DBFactory::RegisterDataStructure("wtree", NewWTreeDB);

} // namespace ycsbc