#include "op_catalog.h"

#include <string_view>

namespace ycsbc {

const OpDef kOpDefs[Operation::MAXOPTYPE + 1] = {
    /* INSERT */ {"INSERT", true, true, true, false, false,
                  PayloadKind::FIELDS},
    /* READ */ {"READ", true, false, false, false, false, PayloadKind::NONE},
    /* UPDATE */
    {"UPDATE", true, false, true, true, false, PayloadKind::FIELDS},
    /* SCAN */ {"SCAN", true, false, false, false, true, PayloadKind::SCAN_LEN},
    /* READMODIFYWRITE */
    {"READMODIFYWRITE", true, false, true, true, false, PayloadKind::FIELDS},
    /* DELETE */
    {"DELETE", false, false, false, false, false, PayloadKind::NONE},
    /* BEGIN_TXN */
    {"BEGIN_TXN", false, false, false, false, false, PayloadKind::NONE},
    /* COMMIT_TXN */
    {"COMMIT_TXN", false, false, false, false, false, PayloadKind::NONE},
    /* ROLLBACK_TXN */
    {"ROLLBACK_TXN", false, false, false, false, false, PayloadKind::NONE},
    /* INSERT_FAILED */
    {"INSERT-FAILED", false, false, false, false, false, PayloadKind::NONE},
    /* READ_FAILED */
    {"READ-FAILED", false, false, false, false, false, PayloadKind::NONE},
    /* UPDATE_FAILED */
    {"UPDATE-FAILED", false, false, false, false, false, PayloadKind::NONE},
    /* SCAN_FAILED */
    {"SCAN-FAILED", false, false, false, false, false, PayloadKind::NONE},
    /* READMODIFYWRITE_FAILED */
    {"READMODIFYWRITE-FAILED", false, false, false, false, false,
     PayloadKind::NONE},
    /* DELETE_FAILED */
    {"DELETE-FAILED", false, false, false, false, false, PayloadKind::NONE},
    /* MAXOPTYPE */
    {"UNKNOWN", false, false, false, false, false, PayloadKind::NONE},
};

const OpDef &OpDefOf(Operation op) {
    const int idx = static_cast<int>(op);
    if(idx < 0 || idx >= Operation::MAXOPTYPE) {
        return kOpDefs[Operation::MAXOPTYPE];
    }
    return kOpDefs[idx];
}

const std::string_view OpName(Operation op) { return OpDefOf(op).name; }

bool IsClientHandled(Operation op) { return OpDefOf(op).handled_by_client; }

void GenerateOp(Operation op, const GenContext &ctx, GeneratedOp &out) {
    const OpDef &def = OpDefOf(op);
    out.type = op;

    if(def.key_from_insert_seq) {
        const uint64_t key_num = ctx.next_insert_key();
        out.key = ctx.build_key(key_num);
        if(ctx.ack_insert_key) {
            ctx.ack_insert_key(key_num);
        }
    } else {
        out.key = ctx.build_key(ctx.next_txn_key_num());
    }

    switch(def.payload) {
    case PayloadKind::FIELDS:
        if(def.values_all_or_single) {
            if(ctx.write_all_fields)
                ctx.build_values_all(out.values);
            else
                ctx.build_values_single(out.values);
        } else {
            ctx.build_values_all(out.values);
        }
        break;
    case PayloadKind::SCAN_LEN:
        out.scan_len = ctx.next_scan_len();
        break;
    case PayloadKind::NONE:
    default:
        break;
    }
}

uint32_t OpPayloadSize(const GeneratedOp &out) {
    switch(OpDefOf(out.type).payload) {
    case PayloadKind::FIELDS: {
        const uint32_t fields_size =
            static_cast<uint32_t>(out.values.buffer().size());
        return sizeof(uint32_t) + fields_size;
    }
    case PayloadKind::SCAN_LEN:
        return sizeof(uint32_t);
    case PayloadKind::NONE:
    default:
        return 0;
    }
}

} // namespace ycsbc