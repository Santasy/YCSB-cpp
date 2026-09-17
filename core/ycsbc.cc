//
//  ycsbc.cc
//  YCSB-cpp
//
//  Copyright (c) 2020 Youngjae Lee <ls4154.lee@gmail.com>.
//  Copyright (c) 2014 Jinglei Ren <jinglei@ren.systems>.
//

#include <chrono>
#include <cstring>
#include <ctime>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <memory>
#include <ostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "dataset.h"
#include "output.h"
#include "core_workload.h"
#include "client.h"
#include "db_factory.h"
#include "measurements.h"
#include "utils/countdown_latch.h"
#include "utils/rate_limit.h"
#include "utils/timer.h"
#include "utils/utils.h"

void UsageMessage(const char *command);
bool StrStartWith(const char *str, const char *pre);
void ParseCommandLine(int argc, const char *argv[],
                      ycsbc::utils::Properties &props);

int main(const int argc, const char *argv[]) {
    ycsbc::utils::Properties props;
    ParseCommandLine(argc, argv, props);

    const bool do_load = (props.GetProperty("doload", "false") == "true");
    const bool do_transaction =
        (props.GetProperty("dotransaction", "false") == "true");
    if(!do_load && !do_transaction) {
        std::cerr << "No operation to do" << std::endl;
        exit(1);
    }

    int num_threads = stoi(props.GetProperty("threadcount", "1"));

    ycsbc::Measurements *measurements = ycsbc::CreateMeasurements(&props);
    if(measurements == nullptr) {
        std::cerr << "Unknown measurements name" << std::endl;
        exit(1);
    }

    ycsbc::CoreWorkload wl;
    wl.Init(props);

    // Result output format. Default is the legible "human" format so the
    // current benchmark scripts keep parsing; `-p resultformat=csv` switches to
    // a headerless machine-readable series of measured windows (columns
    // phase,operation,ops_count,current_size,time_us,maxrss_kb,overhead[,extra]).
    // `--human` (cli.force_human) always wins, so it can override a
    // properties-file resultformat=csv.
    const bool force_human =
        (props.GetProperty("cli.force_human", "false") == "true");
    const bool csv_mode =
        !force_human && (props.GetProperty("resultformat", "human") == "csv");

    // Optional file to duplicate the *result* stream into (enables a
    // storage/<workload>/<container>/time.<seed>.csv layout). Info chatter is
    // never written here. Missing parent directories are created automatically.
    std::ofstream file_stream;
    std::string output_file = props.GetProperty("output.file", "");
    if(!output_file.empty()) {
        if(!ycsbc::CreateParentDir(output_file)) {
            std::cerr << "Cannot create directory for output.file: "
                      << output_file << std::endl;
            exit(1);
        }
        file_stream.open(output_file, std::ios::out | std::ios::trunc);
        if(!file_stream.is_open()) {
            std::cerr << "Cannot open output.file: " << output_file
                      << std::endl;
            exit(1);
        }
    }

    std::ostream *result_out = &std::cout;
    std::unique_ptr<ycsbc::TeeStream> tee;
    if(file_stream.is_open()) {
        tee.reset(new ycsbc::TeeStream(std::cout.rdbuf(), file_stream.rdbuf()));
        result_out = tee.get();
    }

    // Info chatter (dataset gen/reuse messages, `-s` status): stderr in CSV
    // mode so stdout stays pure CSV; stdout in human mode (current behavior).
    std::ostream &info_os = csv_mode ? std::cerr : std::cout;

    // Adapter-specific series column names, reported via DB::GetStats().extra;
    // written into schema.csv (once) when output.file is set.
    std::vector<std::string> schema_extra_cols;

    // Adapter kind. Data-structure adapters are single-owner and not
    // thread-safe: the runtime drives them with one instance (shared across the
    // load and run phases) and a single thread.
    const std::string db_name = props.GetProperty("dbname", "basic");
    const bool is_data_structure = ycsbc::DBFactory::IsDataStructure(db_name);
    if(is_data_structure && num_threads != 1) {
        info_os << "Data-structure adapter '" << db_name
                << "' runs single-threaded; clamping threadcount from "
                << num_threads << " to 1" << std::endl;
        num_threads = 1;
    }

    // Workloads can restrict the adapter kinds they support via
    // `adapter.kinds=db,ds` (absent/empty = any). This keeps
    // data-structure-only or transaction-only workloads from being run on an
    // unsupported adapter.
    const std::string allowed_kinds = props.GetProperty("adapter.kinds", "");
    if(!allowed_kinds.empty()) {
        const std::string wanted_kind = is_data_structure ? "ds" : "db";
        bool allowed = false;
        std::stringstream kinds(allowed_kinds);
        std::string token;
        while(std::getline(kinds, token, ',')) {
            const size_t begin = token.find_first_not_of(" \t");
            const size_t end = token.find_last_not_of(" \t");
            if(begin == std::string::npos)
                continue;
            token = token.substr(begin, end - begin + 1);
            if(token == wanted_kind ||
               (token == "datastructure" && wanted_kind == "ds") ||
               (token == "database" && wanted_kind == "db")) {
                allowed = true;
            }
        }
        if(!allowed) {
            std::cerr << "Workload does not support adapter kind '"
                      << wanted_kind << "' (adapter.kinds=" << allowed_kinds
                      << "); -db " << db_name << " cannot run it" << std::endl;
            exit(1);
        }
    }

    // print status periodically
    const bool show_status = (props.GetProperty("status", "false") == "true");
    const int status_interval =
        std::stoi(props.GetProperty("status.interval", "10"));

    // Data-structure adapters have no persistence and are created once for both
    // phases; storage engines get a fresh instance per phase/thread below.
    ycsbc::DB *shared_db = nullptr;
    if(is_data_structure) {
        shared_db = ycsbc::DBFactory::CreateDB(&props, measurements);
        if(shared_db == nullptr) {
            std::cerr << "Unknown database name " << db_name << std::endl;
            exit(1);
        }
        shared_db->Init();
    }

    // load phase
    if(do_load) {
        const int total_ops =
            stoi(props[ycsbc::CoreWorkload::RECORD_COUNT_PROPERTY]);

        // Pre-generate all keys and values outside the timed window so the
        // measurement reflects DB cost, not YCSB framework cost (BuildKeyName,
        // BuildValues, RNG, ...).
        ycsbc::Dataset load_dataset(props, wl, 0, true);
        const bool force_generate = ycsbc::utils::StrToBool(
            props.GetProperty("force_generate", "false"));
        const std::string load_dataset_path =
            load_dataset.GetFullPath(total_ops);
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
        // data-structure instance so the run phase still sees the loaded data.
        ycsbc::DB *load_db = shared_db;
        if(load_db == nullptr) {
            load_db = ycsbc::DBFactory::CreateDB(&props, measurements);
            if(load_db == nullptr) {
                std::cerr << "Unknown database name " << db_name << std::endl;
                exit(1);
            }
            load_db->Init();
        }

        const std::string &table = wl.table_name();

        timer.Start();
        load_db->Load(table, load_dataset);
        double runtime = timer.End();

        if(csv_mode) {
            // Bulk load is measured as a single window (operation `total`).
            const ycsbc::DB::StoreStats stats = load_db->GetStats(table);
            ycsbc::EmitSeriesRow(*result_out, "load", "total", total_ops,
                                 stats.current_size, runtime * 1e6,
                                 ycsbc::CurrentMaxRssKb(), stats.overhead_bytes,
                                 stats.extra);
            ycsbc::CollectSchemaCols(schema_extra_cols, stats.extra);
        } else {
            *result_out << "Load runtime(sec): " << runtime << std::endl;
            *result_out << "Load operations(ops): " << total_ops << std::endl;
            *result_out << "Load throughput(ops/sec): " << total_ops / runtime
                        << std::endl;
        }

        if(load_db != shared_db) {
            load_db->Cleanup();
            delete load_db;
        }
    }

    measurements->Reset();
    std::this_thread::sleep_for(
        std::chrono::seconds(stoi(props.GetProperty("sleepafterload", "0"))));

    // transaction phase
    if(do_transaction) {
        // initial ops per second, unlimited if <= 0
        const int64_t ops_limit =
            std::stoi(props.GetProperty("limit.ops", "0"));
        // rate file path for dynamic rate limiting, format "time_stamp_sec
        // new_ops_per_second" per line
        std::string rate_file = props.GetProperty("limit.file", "");

        const int total_ops =
            stoi(props[ycsbc::CoreWorkload::OPERATION_COUNT_PROPERTY]);

        // Compute per-thread op counts up front (needed for pre-generation)
        std::vector<int> txn_thread_ops(num_threads);
        for(int i = 0; i < num_threads; ++i) {
            txn_thread_ops[i] = total_ops / num_threads;
            if(i < total_ops % num_threads)
                txn_thread_ops[i]++;
        }

        // Pre-generate all keys and values outside the timed window so the
        // measurement reflects DB cost, not YCSB framework cost.
        std::vector<std::unique_ptr<ycsbc::Dataset>> txn_datasets;
        const bool force_generate = ycsbc::utils::StrToBool(
            props.GetProperty("force_generate", "false"));
        for(int i = 0; i < num_threads; ++i) {
            txn_datasets.emplace_back(new ycsbc::Dataset(props, wl, i, false));
            ycsbc::Dataset &dataset = *txn_datasets.back();
            const int thread_ops = txn_thread_ops[i];
            const std::string dataset_path = dataset.GetFullPath(thread_ops);

            bool should_generate = false;
            std::string reason;
            if(force_generate) {
                should_generate = true;
                reason = "force_generate=true";
            } else {
                struct stat buffer;
                if(stat(dataset_path.c_str(), &buffer) != 0) {
                    should_generate = true;
                    reason = "dataset file missing";
                } else if(!dataset.IsValidForOpCount(thread_ops)) {
                    should_generate = true;
                    reason = "dataset header count mismatch";
                }
            }

            if(should_generate) {
                info_os << "Generating transaction dataset for thread " << i
                        << ": " << reason << " (" << dataset_path << ")"
                        << std::endl;
                txn_datasets.back()->Generate(txn_thread_ops[i]);
            } else {
                info_os << "Reusing existing transaction dataset for thread "
                        << i << ": " << dataset_path << std::endl;
            }
            // txn_datasets.back()->DEBUG(txn_thread_ops[i]);
            txn_datasets.back()->Open(txn_thread_ops[i]);
        }

        // Create fresh DB instances for the transaction phase, or reuse the
        // shared data-structure instance (single-threaded).
        std::vector<ycsbc::DB *> dbs;
        if(shared_db != nullptr) {
            dbs.push_back(shared_db);
        } else {
            for(int i = 0; i < num_threads; i++) {
                ycsbc::DB *db =
                    ycsbc::DBFactory::CreateDB(&props, measurements);
                if(db == nullptr) {
                    std::cerr << "Unknown database name " << db_name
                              << std::endl;
                    exit(1);
                }
                dbs.push_back(db);
            }
        }

        ycsbc::utils::CountDownLatch latch(num_threads);
        ycsbc::utils::Timer<double> timer;

        // Initialize all DB instances before the timed window (the shared
        // data-structure instance was already initialized above)
        for(int i = 0; i < num_threads && shared_db == nullptr; ++i) {
            dbs[i]->Init();
        }

        std::future<void> status_future;
        if(show_status) {
            status_future =
                std::async(std::launch::async, ycsbc::StatusThread,
                           measurements, &latch, status_interval, &info_os);
        }
        std::vector<std::future<int>> client_threads;
        std::vector<ycsbc::utils::RateLimiter *> rate_limiters;

        timer.Start();
        for(int i = 0; i < num_threads; ++i) {
            ycsbc::utils::RateLimiter *rlim = nullptr;
            if(ops_limit > 0 || rate_file != "") {
                int64_t per_thread_ops = ops_limit / num_threads;
                rlim = new ycsbc::utils::RateLimiter(per_thread_ops,
                                                     per_thread_ops);
            }
            rate_limiters.push_back(rlim);
            client_threads.emplace_back(std::async(
                std::launch::async, ycsbc::ClientThread, dbs[i], &wl,
                txn_thread_ops[i], &latch, rlim, txn_datasets[i].get()));
        }

        std::future<void> rlim_future;
        if(rate_file != "") {
            rlim_future = std::async(std::launch::async, ycsbc::RateLimitThread,
                                     rate_file, rate_limiters, &latch);
        }

        assert((int)client_threads.size() == num_threads);

        int sum = 0;
        for(auto &n : client_threads) {
            assert(n.valid());
            sum += n.get();
        }
        double runtime = timer.End();

        if(show_status) {
            status_future.wait();
        }

        if(csv_mode) {
            // One series row per operation (its measured window), then the
            // total.
            const ycsbc::DB::StoreStats stats =
                dbs[0]->GetStats(wl.table_name());
            const long maxrss_kb = ycsbc::CurrentMaxRssKb();
            for(const auto &w : measurements->GetOpWindows()) {
                ycsbc::EmitSeriesRow(*result_out, "run", w.op, w.count,
                                     stats.current_size, w.total_ns / 1000.0,
                                     maxrss_kb, stats.overhead_bytes,
                                     stats.extra);
            }
            ycsbc::EmitSeriesRow(*result_out, "run", "total", sum,
                                 stats.current_size, runtime * 1e6, maxrss_kb,
                                 stats.overhead_bytes, stats.extra);
            ycsbc::CollectSchemaCols(schema_extra_cols, stats.extra);
        } else {
            *result_out << measurements->GetStatusMsg() << std::endl;
            *result_out << "Run runtime(sec): " << runtime << std::endl;
            *result_out << "Run operations(ops): " << sum << std::endl;
            *result_out << "Run throughput(ops/sec): " << sum / runtime
                        << std::endl;
        }

        // Cleanup and delete all DB instances after the timed window. The
        // shared data-structure instance is cleaned up once, after both phases.
        if(shared_db == nullptr) {
            for(int i = 0; i < num_threads; ++i) {
                dbs[i]->Cleanup();
                delete dbs[i];
            }
        }
    }

    if(shared_db != nullptr) {
        shared_db->Cleanup();
        delete shared_db;
    }

    if(csv_mode && file_stream.is_open()) {
        ycsbc::EnsureSchemaFile(output_file, schema_extra_cols);
    }
}

void ParseCommandLine(int argc, const char *argv[],
                      ycsbc::utils::Properties &props) {
    int argindex = 1;
    while(argindex < argc && StrStartWith(argv[argindex], "-")) {
        if(strcmp(argv[argindex], "-load") == 0) {
            props.SetProperty("doload", "true");
            argindex++;
        } else if(strcmp(argv[argindex], "-run") == 0 ||
                  strcmp(argv[argindex], "-t") == 0) {
            props.SetProperty("dotransaction", "true");
            argindex++;
        } else if(strcmp(argv[argindex], "-threads") == 0) {
            argindex++;
            if(argindex >= argc) {
                UsageMessage(argv[0]);
                std::cerr << "Missing argument value for -threads" << std::endl;
                exit(0);
            }
            props.SetProperty("threadcount", argv[argindex]);
            argindex++;
        } else if(strcmp(argv[argindex], "-db") == 0) {
            argindex++;
            if(argindex >= argc) {
                UsageMessage(argv[0]);
                std::cerr << "Missing argument value for -db" << std::endl;
                exit(0);
            }
            props.SetProperty("dbname", argv[argindex]);
            argindex++;
        } else if(strcmp(argv[argindex], "-P") == 0) {
            argindex++;
            if(argindex >= argc) {
                UsageMessage(argv[0]);
                std::cerr << "Missing argument value for -P" << std::endl;
                exit(0);
            }
            std::string filename(argv[argindex]);
            std::ifstream input(argv[argindex]);
            try {
                props.Load(input);
            } catch(const std::string &message) {
                std::cerr << message << std::endl;
                exit(0);
            }
            input.close();
            argindex++;
        } else if(strcmp(argv[argindex], "-p") == 0) {
            argindex++;
            if(argindex >= argc) {
                UsageMessage(argv[0]);
                std::cerr << "Missing argument value for -p" << std::endl;
                exit(0);
            }
            // Here we read any special parameter for the workloads.
            std::string prop(argv[argindex]);
            size_t eq = prop.find('=');
            if(eq == std::string::npos) {
                std::cerr << "Argument '-p' expected to be in key=value format "
                             "(e.g., -p operationcount=99999)"
                          << std::endl;
                exit(0);
            }
            props.SetProperty(ycsbc::utils::Trim(prop.substr(0, eq)),
                              ycsbc::utils::Trim(prop.substr(eq + 1)));
            argindex++;
        } else if(strcmp(argv[argindex], "-s") == 0) {
            props.SetProperty("status", "true");
            argindex++;
        } else if(strcmp(argv[argindex], "--human") == 0) {
            props.SetProperty("cli.force_human", "true");
            argindex++;
        } else {
            UsageMessage(argv[0]);
            std::cerr << "Unknown option '" << argv[argindex] << "'"
                      << std::endl;
            exit(0);
        }
    }

    if(argindex == 1 || argindex != argc) {
        UsageMessage(argv[0]);
        exit(0);
    }
}

void UsageMessage(const char *command) {
    std::cout
        << "Usage: " << command
        << " [options]\n"
           "Options:\n"
           "  -load: run the loading phase of the workload\n"
           "  -t: run the transactions phase of the workload\n"
           "  -run: same as -t\n"
           "  -threads n: execute using n threads (default: 1)\n"
           "  -db dbname: specify the name of the DB to use (default: basic)\n"
           "  -P propertyfile: load properties from the given file. Multiple "
           "files can\n"
           "                   be specified, and will be processed in the "
           "order "
           "specified\n"
           "  -p name=value: specify a property to be passed to the DB and "
           "workloads\n"
           "                 multiple properties can be specified, and "
           "override "
           "any\n"
           "                 values in the propertyfile\n"
           "  -s: print status every 10 seconds (use status.interval prop to "
           "override)\n"
           "  --human: force the human-readable output format (default). "
           "Overrides\n"
           "           -p resultformat=csv, which emits headerless series "
           "rows\n"
           "           "
           "(phase,operation,ops_count,current_size,time_us,maxrss_kb,\n"
           "           overhead plus adapter-specific columns; see schema.csv)"
        << std::endl;
}

inline bool StrStartWith(const char *str, const char *pre) {
    return strncmp(str, pre, strlen(pre)) == 0;
}
