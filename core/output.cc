//
//  output.cc
//  YCSB-cpp
//
//  Result-output helpers, see output.h.
//

#include "core/output.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <sys/resource.h>

namespace ycsbc {

std::string FormatDouble(double v) {
    std::ostringstream s;
    s << v;
    return s.str();
}

long CurrentMaxRssKb() {
    struct rusage usage;
    getrusage(RUSAGE_SELF, &usage);
    return usage.ru_maxrss;
}

bool CreateParentDir(const std::string &path) {
    namespace fs = std::filesystem;
    fs::path parent = fs::path(path).parent_path();
    if(parent.empty())
        return true;
    std::error_code ec;
    fs::create_directories(parent, ec);
    return !ec;
}

void EmitSeriesRow(
    std::ostream &out, const std::string &phase, const std::string &operation,
    uint64_t ops_count, uint64_t current_size, double time_us, long maxrss_kb,
    uint64_t overhead_bytes,
    const std::vector<std::pair<std::string, std::string>> &extra) {
    out << phase << ',' << operation << ',' << ops_count << ',' << current_size
        << ',' << FormatDouble(time_us) << ',' << maxrss_kb << ','
        << overhead_bytes;
    for(const auto &kv : extra) {
        out << ',' << kv.second;
    }
    out << '\n';
}

void CollectSchemaCols(
    std::vector<std::string> &cols,
    const std::vector<std::pair<std::string, std::string>> &extra) {
    for(const auto &kv : extra) {
        if(std::find(cols.begin(), cols.end(), kv.first) == cols.end()) {
            cols.push_back(kv.first);
        }
    }
}

void EnsureSchemaFile(const std::string &output_file,
                      const std::vector<std::string> &extra_cols) {
    namespace fs = std::filesystem;
    if(!CreateParentDir(output_file))
        return;
    fs::path schema_dir = fs::path(output_file).parent_path();
    if(schema_dir.empty())
        schema_dir = ".";
    fs::path schema_file = schema_dir / "schema.csv";
    if(fs::exists(schema_file))
        return;
    std::ofstream schema(schema_file);
    if(!schema.is_open()) {
        std::cerr << "Cannot write schema file: " << schema_file << std::endl;
        return;
    }
    schema
        << "phase,operation,ops_count,current_size,time_us,maxrss_kb,overhead";
    for(const auto &c : extra_cols) {
        schema << ',' << c;
    }
    schema << '\n';
}

} // namespace ycsbc
