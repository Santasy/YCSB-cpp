//
//  output.h
//  YCSB-cpp
//
//  Result-output helpers: result-stream teeing, value formatting, process RSS,
//  and emission of the headerless machine-readable series rows plus the
//  per-container schema file.
//

#ifndef YCSB_C_OUTPUT_H_
#define YCSB_C_OUTPUT_H_

#include <cstdint>
#include <memory>
#include <ostream>
#include <streambuf>
#include <string>
#include <utility>
#include <vector>

namespace ycsbc {

// Tees every write into two streambufs (used to duplicate the result stream
// into an optional output.file while keeping stdout live).
class TeeBuf : public std::streambuf {
 public:
  TeeBuf(std::streambuf* a, std::streambuf* b) : a_(a), b_(b) {}
 protected:
  int_type overflow(int_type c) override {
    if (c == traits_type::eof()) return traits_type::not_eof(c);
    if (a_ && a_->sputc(static_cast<char>(c)) == traits_type::eof()) {
      return traits_type::eof();
    }
    if (b_ && b_->sputc(static_cast<char>(c)) == traits_type::eof()) {
      return traits_type::eof();
    }
    return c;
  }
  int sync() override {
    const int ra = a_ ? a_->pubsync() : 0;
    const int rb = b_ ? b_->pubsync() : 0;
    return (ra == 0 && rb == 0) ? 0 : -1;
  }
 private:
  std::streambuf* a_;
  std::streambuf* b_;
};

class TeeStream : public std::ostream {
 public:
  TeeStream(std::streambuf* a, std::streambuf* b)
      : std::ostream(nullptr), buf_(new TeeBuf(a, b)) {
    rdbuf(buf_.get());
  }
 private:
  std::unique_ptr<TeeBuf> buf_;
};

// Formats a runtime/throughput value like the human output does: default
// stream precision (significant digits), no fixed decimals.
std::string FormatDouble(double v);

// Peak resident set size of this process, kilobytes (Linux RUSAGE_SELF).
long CurrentMaxRssKb();

// Creates the parent directory of `path` if needed (no-op when `path` has no
// parent). Returns false if the directory could not be created.
bool CreateParentDir(const std::string& path);

// Emits one headerless series row:
//   phase,operation,ops_count,current_size,time_us,maxrss_kb,overhead
// followed by any adapter-specific extra columns (values only; names live in
// the per-container schema.csv). `time_us` is the window wall-time; `maxrss_kb`
// and `current_size` are sampled at the end of the measured window.
void EmitSeriesRow(std::ostream& out, const std::string& phase,
                   const std::string& operation, uint64_t ops_count,
                   uint64_t current_size, double time_us, long maxrss_kb,
                   uint64_t overhead_bytes,
                   const std::vector<std::pair<std::string, std::string>>& extra);

// Records optional column names (in first-seen order) so the schema file for
// this container can describe them.
void CollectSchemaCols(std::vector<std::string>& cols,
                       const std::vector<std::pair<std::string, std::string>>& extra);

// Writes <dir>/schema.csv (header line describing the series columns) next to
// output.file. Only created if it does not already exist, so a container's
// schema is written once and never clobbered by later runs.
void EnsureSchemaFile(const std::string& output_file,
                      const std::vector<std::string>& extra_cols);

}  // namespace ycsbc

#endif  // YCSB_C_OUTPUT_H_
