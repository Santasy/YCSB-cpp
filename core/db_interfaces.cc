//
//  db_interfaces.cc
//  YCSB-cpp
//

#include "db_interfaces.h"

#include "dataset.h"

namespace ycsbc {

DBInterface::Status DBInterface::Load(const std::string &table,
                                      Dataset &batch) {
  const int n = batch.OpCount();
  for (int i = 0; i < n; ++i) {
    const auto &item = batch.Next();
    const Slice &data = item.values.data();
    Status s = Put(table, item.key, data);
    if (s != kOK) {
      return s;
    }
  }
  return kOK;
}

} // namespace ycsbc
