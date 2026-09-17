//
//  db_interfaces.h
//  YCSB-cpp
//
//  Backend interfaces for benchmark targets.
//
//  `DBInterface` is the primitive, single-owner ordered key/value contract that
//  every backend implements: a data structure (std::map, a btree, ...) or a
//  storage engine. It carries the shared vocabulary (`Status`, `Field`,
//  `StoreStats`) and has no notion of per-thread instances, transactions or
//  persistence.
//
//  `DB` (see core/db_database.h) specialises this base with YCSB row semantics
//  (Fields, RMW merge, kSkip) and is what the client hot loop talks to.
//
//  Data-structure adapters are expected to implement only the raw primitives
//  here and are NOT required to be thread-safe: the runtime runs them with a
//  single instance and a single thread (see core/ycsbc.cc).
//

#ifndef YCSB_C_DB_INTERFACES_H_
#define YCSB_C_DB_INTERFACES_H_

#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

#include "utils/fields.h"
#include "utils/properties.h"

namespace ycsbc {

class Dataset;

///
/// Primitive ordered key/value backend contract.
///
/// Single-owner: an instance is not shared between threads, and the runtime
/// never assumes thread-safety from a DBInterface implementation.
///
class DBInterface {
  public:
    enum Status {
        kOK = 0,
        kError,
        kNotFound,
        kNotImplemented,
        kSkip // Operation intentionally skipped (e.g., Read in RMW when Update
              // reads anyway)
    };

    struct Field {
        std::string name;
        std::string value;
    };

    ///
    /// In-memory store statistics reported into the machine-readable series
    /// output (columns: current_size, overhead, plus optional per-structure
    /// extra columns such as tree height / leaf count).
    ///
    struct StoreStats {
        uint64_t current_size = 0; // rows/records currently stored
        uint64_t overhead_bytes =
            0; // container overhead beyond raw payload bytes
        std::vector<std::pair<std::string, std::string>> extra; // optional cols
    };

    ///
    /// Initializes any state for accessing this backend.
    ///
    virtual void Init() {}
    ///
    /// Clears any state for accessing this backend.
    ///
    virtual void Cleanup() {}

    ///
    /// Reads the raw value stored under `key`.
    ///
    /// @return kOK on success, kNotFound when the key is absent.
    ///
    virtual Status Get(const std::string &table, Slice key,
                       std::string &value) = 0;
    ///
    /// Writes `value` under `key` (insert-or-overwrite).
    ///
    virtual Status Put(const std::string &table, Slice key, Slice value) = 0;
    ///
    /// Removes `key`.
    ///
    virtual Status Erase(const std::string &table, Slice key) = 0;
    ///
    /// Ordered range read: up to `count` raw values starting at `key`
    /// (inclusive). Implementations return values in key order.
    ///
    virtual Status Range(const std::string &table, Slice key, int count,
                         std::vector<std::string> &out) = 0;

    ///
    /// Bulk-loads a set of pre-generated operations.
    /// The default implementation falls back to per-op `Put`; backends with a
    /// more efficient bulk path (WriteBatch, single cursor transaction, ...)
    /// override this.
    ///
    virtual Status Load(const std::string &table, Dataset &batch);

    ///
    /// Explicit transaction callbacks. Backends that cannot honor them keep the
    /// default `kNotImplemented` so batch wiring in client.h is
    /// backend-agnostic.
    ///
    virtual Status BeginTransaction() { return kNotImplemented; }
    virtual Status CommitTransaction() { return kNotImplemented; }
    virtual Status RollbackTransaction() { return kNotImplemented; }

    ///
    /// Returns store statistics for the given table.
    ///
    virtual StoreStats GetStats(const std::string &table) {
        return StoreStats();
    }

    virtual ~DBInterface() {}

    void SetProps(utils::Properties *props) { props_ = props; }

  protected:
    utils::Properties *props_;
};

///
/// Optional mixin centralizing the "one shared native handle + refcount,
/// guarded by a mutex" pattern used by the storage-engine adapters (each of
/// which currently declares its own statics). Opt-in: adopting it must not
/// change adapter behavior.
///
/// State is per instantiation (per `Handle`), so two adapters wrapping the same
/// handle type still share one guard.
///
template <typename Handle> class SharedBackend {
  protected:
    static Handle *handle_;
    static int ref_cnt_;
    static std::mutex mutex_;
};

template <typename Handle> Handle *SharedBackend<Handle>::handle_ = nullptr;
template <typename Handle> int SharedBackend<Handle>::ref_cnt_ = 0;
template <typename Handle> std::mutex SharedBackend<Handle>::mutex_;

} // namespace ycsbc

#endif // YCSB_C_DB_INTERFACES_H_
