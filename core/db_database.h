//
//  db_database.h
//  YCSB-cpp
//
//  Copyright (c) 2020 Youngjae Lee <ls4154.lee@gmail.com>.
//  Copyright (c) 2014 Jinglei Ren <jinglei@ren.systems>.
//
//  YCSB row-semantics layer on top of the primitive DBInterface (core/
//  db_interfaces.h). `DB` is what the client hot loop talks to: it works in
//  terms of `Fields`, handles RMW merging and the kSkip convention, and leaves
//  raw key/value storage to the backend.
//
//  Storage-engine adapters derive from `DB` and normally override the row
//  methods directly (they need per-format layouts). `RowStoreDB` adapts a bare
//  DBInterface (a data structure) up to the row API by inheriting DB's default
//  implementations and delegating the raw primitives to the wrapped store.
//

#ifndef YCSB_C_DB_DATABASE_H_
#define YCSB_C_DB_DATABASE_H_

#include <string>
#include <unordered_set>
#include <vector>

#include "db_interfaces.h"
#include "utils/fields.h"

namespace ycsbc {

class Dataset;

///
/// YCSB row interface. per-thread DB instance.
///
class DB : public DBInterface {
 public:
  ///
  /// Flushes any pending writes without closing the backend.
  /// Called at the end of each client thread's work to ensure partial batches
  /// are committed before the thread exits (prevents lock leaks on shared DBs).
  ///
  virtual void FlushPending() { }

  //
  // Row operations. The default implementations below are expressed purely in
  // terms of the raw DBInterface primitives (Get/Put/Erase/Range), i.e. the
  // "single entry" layout: the whole row is one value blob. Backends that need
  // a row/column layout keep overriding these directly.
  //

  virtual Status Read(const std::string &table, Slice key,
                   const std::unordered_set<std::string> *fields,
                   Fields &result, bool rmw = false) {
    // When rmw is true the caller's Update re-reads and merges internally.
    if (rmw) return kSkip;

    std::string data;
    Status s = Get(table, key, data);
    if (s != kOK) return s;
    ReadonlyFields readonly(data.data(), data.size());
    if (fields != nullptr) {
      readonly.filter(result, *fields);
    } else {
      result = readonly;
    }
    return kOK;
  }

  virtual Status Scan(const std::string &table, Slice key,
                   int record_count, const std::unordered_set<std::string> *fields,
                   std::vector<Fields> &result) {
    std::vector<std::string> rows;
    Status s = Range(table, key, record_count, rows);
    if (s != kOK) return s;

    result.clear();
    result.reserve(rows.size());
    for (const std::string &row : rows) {
      result.emplace_back();
      Fields &values = result.back();
      ReadonlyFields readonly(row.data(), row.size());
      if (fields != nullptr) {
        readonly.filter(values, *fields);
      } else {
        values = readonly;
      }
    }
    return kOK;
  }

  virtual Status Update(const std::string &table, Slice key,
                     const ReadonlyFields &values) {
    std::string data;
    Status s = Get(table, key, data);
    if (s != kOK) return s;

    ReadonlyFields readonly(data.data(), data.size());
    updated_fields_ = readonly;
    updated_fields_.update(values);
    return Put(table, key, Slice(updated_fields_.buffer()));
  }

  virtual Status Insert(const std::string &table, Slice key,
                     const ReadonlyFields &values) {
    return Put(table, key, values.data());
  }

  virtual Status Delete(const std::string &table, Slice key) {
    return Erase(table, key);
  }

  // Raw primitives default to "not a raw store": storage-engine adapters that
  // only override the row methods remain concrete, while data-structure
  // adapters implement these instead.
  Status Get(const std::string &, Slice, std::string &) override {
    return kNotImplemented;
  }
  Status Put(const std::string &, Slice, Slice) override {
    return kNotImplemented;
  }
  Status Erase(const std::string &, Slice) override {
    return kNotImplemented;
  }
  Status Range(const std::string &, Slice, int,
               std::vector<std::string> &) override {
    return kNotImplemented;
  }

 protected:
  Fields updated_fields_;
};

///
/// Adapts a bare DBInterface (e.g. a data structure) to the row API: inherits
/// DB's default row implementations and forwards the raw primitives.
///
class RowStoreDB : public DB {
 public:
  explicit RowStoreDB(DBInterface *store) : store_(store) {}
  ~RowStoreDB() { delete store_; }

  void Init() override { store_->Init(); }
  void Cleanup() override { store_->Cleanup(); }
  void FlushPending() override { }

  Status Get(const std::string &table, Slice key,
             std::string &value) override {
    return store_->Get(table, key, value);
  }
  Status Put(const std::string &table, Slice key, Slice value) override {
    return store_->Put(table, key, value);
  }
  Status Erase(const std::string &table, Slice key) override {
    return store_->Erase(table, key);
  }
  Status Range(const std::string &table, Slice key, int count,
               std::vector<std::string> &out) override {
    return store_->Range(table, key, count, out);
  }
  Status Load(const std::string &table, Dataset &batch) override {
    return store_->Load(table, batch);
  }
  StoreStats GetStats(const std::string &table) override {
    return store_->GetStats(table);
  }

 private:
  DBInterface *store_;
};

} // ycsbc

#endif // YCSB_C_DB_DATABASE_H_
