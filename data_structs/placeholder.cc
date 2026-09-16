// ycsb_data_structs placeholder translation unit.
// Keeps the OBJECT target non-empty so CMake accepts it, even when no
// data-structure adapter bindings are enabled. Future std::map/std::set
// (etc.) adapter bindings land in this directory.

namespace ycsbc {
// Version anchor so the TU is never empty and the target always has content.
int ycsb_data_structs_version() {
  return 1;
}
}  // namespace ycsbc
