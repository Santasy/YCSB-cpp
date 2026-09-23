#ifndef _YCSBC_H_
#define _YCSBC_H_

#include <iostream>
#include <ostream>
#include <string>
#include <vector>

#include "dataset.h"
#include "output.h"
#include "core_workload.h"
#include "db_factory.h"
#include "measurements.h"
#include "utils/timer.h"
#include "utils/utils.h"

namespace ycsbc {

namespace Pipeline {

bool StepLoad(ycsbc::utils::Properties &props, ycsbc::CoreWorkload &workload,
              const std::string_view &db_name, ycsbc::DB *shared_db,
              std::vector<std::string> &schema_extra_cols,
              ycsbc::Measurements *measurements,
              std::ostream *result_os = &std::cout,
              std::ostream &info_os = std::cout, bool outstyle_csv = true) {
    const int total_ops =
        stoi(props[ycsbc::CoreWorkload::RECORD_COUNT_PROPERTY]);

    // Pre-generate all keys and values outside the timed window so the
    // measurement reflects DB cost, not YCSB framework cost
    // (BuildKeyName, BuildValues, RNG, ...).
    ycsbc::Dataset load_dataset(props, workload, 0, true);
    const bool force_generate =
        ycsbc::utils::StrToBool(props.GetProperty("force_generate", "false"));
    const std::string load_dataset_path = load_dataset.GetFullPath(total_ops);
    bool should_generate = false;
    std::string reason;
    if(force_generate) {
        should_generate = true;
        reason = "force_generate=true";
    } else {
        struct stat buffer;
        if(stat(load_dataset_path.c_str(), &buffer) != 0) {
            should_generate = true;
            reason = "dataset file missing";
        } else if(!load_dataset.IsValidForOpCount(total_ops)) {
            should_generate = true;
            reason = "dataset header count mismatch";
        }
    }

    if(should_generate) {
        info_os << "Generating load dataset: " << reason << " ("
                << load_dataset_path << ")" << std::endl;
        load_dataset.Generate(total_ops);
    } else {
        info_os << "Reusing existing load dataset: " << load_dataset_path
                << std::endl;
    }
    load_dataset.Open(total_ops);

    ycsbc::utils::Timer<double> timer;

    // Use a dedicated DB instance for the load phase, or the shared
    // data-structure instance so the run phase still sees the loaded
    // data.
    ycsbc::DB *load_db = shared_db;
    if(load_db == nullptr) {
        load_db = ycsbc::DBFactory::CreateDB(&props, measurements);
        if(load_db == nullptr) {
            std::cerr << "Unknown database name " << db_name << std::endl;
            return false;
        }
        load_db->Init();
    }

    const std::string &table = workload.table_name();

    timer.Start();
    load_db->Load(table, load_dataset);
    double runtime = timer.End();

    if(outstyle_csv) {
        // Bulk load is measured as a single window (operation `total`).
        const ycsbc::DB::StoreStats stats = load_db->GetStats(table);
        ycsbc::EmitSeriesRow(*result_os, "load", "total", total_ops,
                             stats.current_size, runtime * 1e6,
                             ycsbc::CurrentMaxRssKb(), stats.overhead_bytes,
                             stats.extra);
        ycsbc::CollectSchemaCols(schema_extra_cols, stats.extra);
    } else {
        *result_os << "Load runtime(sec): " << runtime << std::endl;
        *result_os << "Load operations(ops): " << total_ops << std::endl;
        *result_os << "Load throughput(ops/sec): " << total_ops / runtime
                   << std::endl;
    }

    if(load_db != shared_db) {
        load_db->Cleanup();
        delete load_db;
    }
    return true;
}

} // namespace Pipeline

} // namespace ycsbc

#endif