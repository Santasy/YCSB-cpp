//
//  client.h
//  YCSB-cpp
//
//  Copyright (c) 2020 Youngjae Lee <ls4154.lee@gmail.com>.
//  Copyright (c) 2014 Jinglei Ren <jinglei@ren.systems>.
//

#ifndef YCSB_C_CLIENT_H_
#define YCSB_C_CLIENT_H_

#include <iostream>
#include <string>

#include "utils/countdown_latch.h"
#include "utils/rate_limit.h"
#include "utils/utils.h"

#include "dataset.h"
#include "core_workload.h"
#include "db_database.h"
#include "measurements.h"

namespace ycsbc {

void RateLimitThread(std::string rate_file,
                     std::vector<ycsbc::utils::RateLimiter *> rate_limiters,
                     ycsbc::utils::CountDownLatch *latch) {
    std::ifstream ifs;
    ifs.open(rate_file);

    if(!ifs.is_open()) {
        ycsbc::utils::Exception("failed to open: " + rate_file);
    }

    int64_t num_threads = rate_limiters.size();

    int64_t last_time = 0;
    while(!ifs.eof()) {
        int64_t next_time;
        int64_t next_rate;
        ifs >> next_time >> next_rate;

        if(next_time <= last_time) {
            ycsbc::utils::Exception("invalid rate file");
        }

        bool done = latch->AwaitFor(next_time - last_time);
        if(done) {
            break;
        }
        last_time = next_time;

        for(auto x : rate_limiters) {
            x->SetRate(next_rate / num_threads);
        }
    }
}

inline int ClientThread(ycsbc::DB *db, CoreWorkload *wl, const int num_ops,
                        utils::CountDownLatch *latch, utils::RateLimiter *rlim,
                        ycsbc::Dataset *dataset) {
    try {
        int ops = 0;

        // Pre-generated path: hot loop contains only DB calls, no key/value
        // generation. Pre-generation is mandatory so the measurement reflects
        // DB cost, not framework cost.
        Fields result_buf;
        std::vector<Fields> scan_result_buf;
        const std::string &table = wl->table_name();
        const int batch_size = wl->batch_size();

        for(int i = 0; i < num_ops; i += batch_size) {
            if(rlim) {
                rlim->Consume(batch_size);
            }

            int batch_end = std::min(i + batch_size, num_ops);
            int batch_len = batch_end - i;

            // Begin transaction for this batch.  The adapter may decide to
            // optimise single-operation batches (batch_size==1) differently
            // from multi-operation batches.
            db->BeginTransaction();

            for(int j = 0; j < batch_len; ++j) {
                const auto &item = dataset->Next();
                const auto &values = item.values;

                switch(item.type) {
                case CoreWorkload::WorkItem::OpType::INSERT:
                    db->Insert(table, item.key, values);
                    break;
                case CoreWorkload::WorkItem::OpType::UPDATE:
                    db->Update(table, item.key, values);
                    break;
                case CoreWorkload::WorkItem::OpType::READ:
                    result_buf.clear();
                    db->Read(table, item.key, nullptr, result_buf);
                    break;
                case CoreWorkload::WorkItem::OpType::SCAN:
                    scan_result_buf.clear();
                    db->Scan(table, item.key, item.scan_len, nullptr,
                             scan_result_buf);
                    break;
                case CoreWorkload::WorkItem::OpType::READMODIFYWRITE:
                    result_buf.clear();
                    db->Read(table, item.key, nullptr, result_buf, true);
                    db->Update(table, item.key, item.values);
                    break;
                }
                ops++;
            }

            // Commit transaction for this batch.
            db->CommitTransaction();
        }

        // Flush any pending writes (e.g. partial batch) so locks are released
        // before this thread exits.
        db->FlushPending();

        latch->CountDown();
        return ops;
    } catch(const utils::Exception &e) {
        std::cerr << "Caught exception: " << e.what() << std::endl;
        exit(1);
    }
}

void StatusThread(ycsbc::Measurements *measurements,
                  ycsbc::utils::CountDownLatch *latch, int interval,
                  std::ostream *out) {
    using namespace std::chrono;
    time_point<system_clock> start = system_clock::now();
    bool done = false;
    while(1) {
        time_point<system_clock> now = system_clock::now();
        std::time_t now_c = system_clock::to_time_t(now);
        duration<double> elapsed_time = now - start;

        *out << std::put_time(std::localtime(&now_c), "%F %T") << ' '
             << static_cast<long long>(elapsed_time.count()) << " sec: ";

        *out << measurements->GetStatusMsg() << std::endl;

        if(done) {
            break;
        }
        done = latch->AwaitFor(interval);
    };
}

} // namespace ycsbc

#endif // YCSB_C_CLIENT_H_