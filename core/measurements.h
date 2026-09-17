//
//  measurements.h
//  YCSB-cpp
//
//  Copyright (c) 2020 Youngjae Lee <ls4154.lee@gmail.com>.
//

#ifndef YCSB_C_MEASUREMENTS_H_
#define YCSB_C_MEASUREMENTS_H_

#include "core_workload.h"
#include "utils/properties.h"

#include <atomic>
#include <string>
#include <utility>
#include <vector>

#ifdef HDRMEASUREMENT
#include <hdr/hdr_histogram.h>
#endif

typedef unsigned int uint;

namespace ycsbc {

// One measured window for a single operation: the merged sample count and the
// accumulated execution wall-time (nanoseconds) spent on that operation across
// all worker threads between two Reset() calls. Used by the machine-readable
// (series CSV) output; `time_us` for a window is total_ns / 1000.0.
struct OpWindow {
    std::string op;    // lowercased operation name, e.g. "read"
    uint64_t count;    // number of operations in the window
    uint64_t total_ns; // accumulated execution wall-time, nanoseconds
};

class Measurements {
  public:
    virtual void Report(Operation op, uint64_t latency) = 0;
    virtual std::string GetStatusMsg() = 0;
    // Per-operation window stats. Operations with no recorded samples are
    // omitted.
    virtual std::vector<OpWindow> GetOpWindows() = 0;
    virtual void Reset() = 0;
};

class BasicMeasurements : public Measurements {
  public:
    BasicMeasurements();
    void Report(Operation op, uint64_t latency) override;
    std::string GetStatusMsg() override;
    std::vector<OpWindow> GetOpWindows() override;
    void Reset() override;

  private:
    std::atomic<uint> count_[MAXOPTYPE];
    std::atomic<uint64_t> latency_sum_[MAXOPTYPE];
    std::atomic<uint64_t> latency_min_[MAXOPTYPE];
    std::atomic<uint64_t> latency_max_[MAXOPTYPE];
};

#ifdef HDRMEASUREMENT
class HdrHistogramMeasurements : public Measurements {
  public:
    HdrHistogramMeasurements();
    void Report(Operation op, uint64_t latency) override;
    std::string GetStatusMsg() override;
    std::vector<OpWindow> GetOpWindows() override;
    void Reset() override;

  private:
    hdr_histogram *histogram_[MAXOPTYPE];
};
#endif

Measurements *CreateMeasurements(utils::Properties *props);

} // namespace ycsbc

#endif // YCSB_C_MEASUREMENTS
