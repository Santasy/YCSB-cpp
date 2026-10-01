#ifndef _OP_CATALOG_H_
#define _OP_CATALOG_H_

#include <functional>
#include <string>
#include <string_view>
#include <sys/types.h>

#include "utils/fields.h"

namespace ycsbc {

/// The set of operation types understood by the framework. This is the single
/// source of truth for operation identities; all op-related helpers live in
/// this header (see OpDef / OpName / IsClientHandled / GenerateOp below).
enum Operation {
    INSERT = 0,
    READ,
    UPDATE,
    SCAN,
    READMODIFYWRITE,
    DELETE,
    BEGIN_TXN,
    COMMIT_TXN,
    ROLLBACK_TXN,
    INSERT_FAILED,
    READ_FAILED,
    UPDATE_FAILED,
    SCAN_FAILED,
    READMODIFYWRITE_FAILED,
    DELETE_FAILED,
    MAXOPTYPE
};

/// The kind of per-op payload stored in the serialized dataset file (and
/// carried by a generated op). Drives (de)serialization generically instead of
/// a per-op switch.
enum class PayloadKind { FIELDS, SCAN_LEN, NONE };

/// Static description of one operation: how it is named, whether the client
/// executor handles it, and how its data (key, values, scan length) is
/// generated and serialized. This is the single place that declares per-op
/// behavior; generation and (de)serialization read these flags rather than
/// duplicating op-specific switches.
struct OpDef {
    std::string_view name;
    bool handled_by_client;
    bool key_from_insert_seq; // key drawn from the insert-key sequence (+ack)
    bool write_values;        // op carries a Fields payload (INSERT/UPDATE/RMW)
    bool values_all_or_single; // honor write_all_fields_ (UPDATE/RMW); INSERT
                               // always all
    bool has_scan_len;         // op carries a scan length (SCAN)
    PayloadKind payload;
};

/// One table entry per Operation value, in enum order, plus a sentinel entry
/// at index MAXOPTYPE for out-of-range lookups. See op_catalog.cc.
extern const OpDef kOpDefs[Operation::MAXOPTYPE + 1];

const OpDef &OpDefOf(Operation op);

/// Return the human-readable name for an Operation enum value.
const std::string_view OpName(Operation op);

/// Return true if the given Operation is handled by the ClientThread switch
/// in core/client.h. Unhandled ops (DELETE, transaction ops, _FAILED variants)
/// fall to the default case.
bool IsClientHandled(Operation op);

/// Abstract inputs a per-op data generator needs. CoreWorkload wires these to
/// its generators/sequences when pre-generating a batch of operations, so the
/// generation logic in op_catalog.cc stays decoupled from workload internals.
struct GenContext {
    std::function<uint64_t()> next_txn_key_num;     // NextTransactionKeyNum()
    std::function<std::string(uint64_t)> build_key; // BuildKeyName(key_num)
    std::function<uint64_t()> next_insert_key;      // load seq OR txn sec seq
    std::function<void(uint64_t)> ack_insert_key;   // no-op for load seq
    std::function<void(Fields &)> build_values_all;
    std::function<void(Fields &)> build_values_single;
    std::function<int()> next_scan_len; // scan_len_chooser_->Next()
    bool write_all_fields;
};

/// A generated operation, filled by GenerateOp from an OpDef + GenContext.
/// `values` is the mutable build-side buffer; on the replay side WorkItem
/// exposes the same data read-only.
struct GeneratedOp {
    Operation type;
    std::string key;
    Fields values;
    int scan_len{0};
};

/// Fill `out` from `def` using `ctx`. Behavior is fully driven by the OpDef
/// flags (no per-op switch). Not valid for ops with key_from_insert_seq when
/// neither sequence is wired; callers must not pass unhandled/unimplemented
/// ops here.
void GenerateOp(Operation op, const GenContext &ctx, GeneratedOp &out);

/// Serialized op-specific payload length for a generated op, based on its
/// PayloadKind: kFields writes [u32 size][bytes], kScanLen writes [u32].
uint32_t OpPayloadSize(const GeneratedOp &out);

} // namespace ycsbc
#endif