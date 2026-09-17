//
//  fields.h
//  YCSB-cpp
//
//  Optimized Fields container that uses contiguous memory buffer
//  instead of std::vector<DB::Field> to eliminate allocations.
//

#ifndef YCSB_C_FIELDS_H_
#define YCSB_C_FIELDS_H_

#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <unordered_set>
#include <vector>

namespace ycsbc {

// Forward declarations
class Fields;

// Lightweight string view similar to leaves::Slice
class Slice {
  public:
    Slice() : data_(nullptr), size_(0) {}
    Slice(const char *data, size_t size) : data_(data), size_(size) {}
    Slice(const std::string &str) : data_(str.data()), size_(str.size()) {}

    const char *data() const { return data_; }
    size_t size() const { return size_; }
    bool empty() const { return size_ == 0; }

    std::string ToString() const { return std::string(data_, size_); }

    bool operator==(const Slice &other) const {
        return size_ == other.size_ &&
               std::memcmp(data_, other.data_, size_) == 0;
    }

  private:
    const char *data_;
    size_t size_;
};

// Read-only Fields container using a Slice as data source
class ReadonlyFields {
  public:
    ReadonlyFields() : data_(nullptr, 0) {}
    explicit ReadonlyFields(const Slice &data) : data_(data) {}
    explicit ReadonlyFields(const char *data, size_t size)
        : data_(data, size) {}

    // Number of fields
    size_t size() const {
        if(data_.size() < sizeof(uint32_t))
            return 0;
        return *reinterpret_cast<const uint32_t *>(data_.data());
    }

    bool empty() const { return size() == 0; }

    // Iterator for reading fields
    class iterator {
      public:
        iterator(const char *ptr, const char *end) : ptr_(ptr), end_(end) {}

        iterator(const std::string &buffer)
            : ptr_(buffer.data() + sizeof(uint32_t)),
              end_(buffer.data() + buffer.size()) {}

        bool operator!=(const iterator &other) const {
            return ptr_ != other.ptr_;
        }

        iterator &operator++() {
            if(ptr_ < end_) {
                uint32_t name_size = *reinterpret_cast<const uint32_t *>(ptr_);
                uint32_t value_size = *reinterpret_cast<const uint32_t *>(
                    ptr_ + sizeof(uint32_t));
                ptr_ += 2 * sizeof(uint32_t) + name_size + value_size;
            }
            return *this;
        }

        // Returns pair of (name_slice, value_slice)
        std::pair<Slice, Slice> operator*() const {
            uint32_t name_size = *reinterpret_cast<const uint32_t *>(ptr_);
            uint32_t value_size =
                *reinterpret_cast<const uint32_t *>(ptr_ + sizeof(uint32_t));

            const char *name_data = ptr_ + 2 * sizeof(uint32_t);
            const char *value_data = name_data + name_size;

            return std::make_pair(Slice(name_data, name_size),
                                  Slice(value_data, value_size));
        }

        inline uint32_t name_size() const {
            return *reinterpret_cast<const uint32_t *>(ptr_);
        }

        inline uint32_t value_size() const {
            return *reinterpret_cast<const uint32_t *>(ptr_ + sizeof(uint32_t));
        }

        inline uint32_t pair_size() const {
            return 2 * sizeof(uint32_t) + name_size() + value_size();
        }

        // Get name slice
        Slice name() const {
            return Slice(ptr_ + 2 * sizeof(uint32_t), name_size());
        }

        // Get value slice
        Slice value() const {
            return Slice(ptr_ + 2 * sizeof(uint32_t) + name_size(),
                         value_size());
        }

        const char *address() const { return ptr_; }
        const char *end() const { return end_; }

      private:
        const char *ptr_;
        const char *end_;
    };

    iterator begin() const {
        if(data_.size() <= sizeof(uint32_t)) {
            return end();
        }
        return iterator(data_.data() + sizeof(uint32_t),
                        data_.data() + data_.size());
    }

    iterator end() const {
        return iterator(data_.data() + data_.size(),
                        data_.data() + data_.size());
    }

    // Filter fields into destination based on field names in the set
    // Copies only fields from this object whose names are in the fields set
    void filter(Fields &dest,
                const std::unordered_set<std::string> &fields) const;

    // Get raw data slice
    const Slice &data() const { return data_; }

  protected:
    Slice data_;
};

// Optimized Fields container using contiguous memory buffer
class Fields : public ReadonlyFields {
  public:
    Fields() {
        buffer_.reserve(2048); // Pre-allocate reasonable size
        // Initialize with count = 0
        buffer_.resize(sizeof(uint32_t));
        *reinterpret_cast<uint32_t *>(&buffer_[0]) = 0;
        data_ = Slice(buffer_.data(), buffer_.size());
    }

    Fields &operator=(const ReadonlyFields &other) {
        if(this != &other) {
            Slice other_data = other.data();
            buffer_.assign(other_data.data(), other_data.size());
            data_ = Slice(buffer_.data(), buffer_.size());
        }
        return *this;
    }

    // Add a field to the buffer
    void push(const std::string &name, const std::string &value) {
        push(Slice(name), Slice(value));
    }

    void push(const Slice &name, const Slice &value) {
        // Format:
        // [count:4][name_size:4][value_size:4][name_data][value_data]...
        uint32_t name_size = static_cast<uint32_t>(name.size());
        uint32_t value_size = static_cast<uint32_t>(value.size());

        // Append sizes and data
        size_t old_size = buffer_.size();
        buffer_.resize(old_size + 2 * sizeof(uint32_t) + name_size +
                       value_size);
        char *ptr = &buffer_[old_size];

        *reinterpret_cast<uint32_t *>(ptr) = name_size;
        ptr += sizeof(uint32_t);
        *reinterpret_cast<uint32_t *>(ptr) = value_size;
        ptr += sizeof(uint32_t);
        std::memcpy(ptr, name.data(), name_size);
        ptr += name_size;
        std::memcpy(ptr, value.data(), value_size);

        // Increment count in header
        uint32_t &count = *reinterpret_cast<uint32_t *>(&buffer_[0]);
        count++;

        // Update data slice
        data_ = Slice(buffer_.data(), buffer_.size());
    }

    // Alias for push() - used by some databases
    void add(const std::string &name, const std::string &value) {
        push(name, value);
    }

    void add(const char *name, const char *value) {
        push(Slice(name, std::strlen(name)), Slice(value, std::strlen(value)));
    }

    void add(const char *name, size_t name_len, const char *value,
             size_t value_len) {
        push(Slice(name, name_len), Slice(value, value_len));
    }

    // Clear all fields but keep capacity
    void clear() {
        buffer_.resize(sizeof(uint32_t));
        *reinterpret_cast<uint32_t *>(&buffer_[0]) = 0;
        data_ = Slice(buffer_.data(), buffer_.size());
    }

    // Reserve capacity in underlying buffer
    void reserve(size_t capacity) { buffer_.reserve(capacity); }

    // Update fields from another Fields object
    // Adds new fields from toupd,ate that don't exist in this
    // Returns a Slice to the update_buffer_ containing the merged result
    Slice update(const ReadonlyFields &toupdate) {
        // Step 1: Initialize update_buffer_ with current fields
        if(update_buffer_.empty()) {
            // First time: copy buffer_ to update_buffer_ by memcpy
            update_buffer_.assign(buffer_.data(), buffer_.size());
        } else {
            // Reuse existing update_buffer_: truncate to buffer_ size
            update_buffer_.resize(buffer_.size());
            std::memcpy(&update_buffer_[0], buffer_.data(), buffer_.size());
        }

        uint32_t count = size();

        // Step 2: Add fields from toupdate that are not in this
        for(auto it = toupdate.begin(); it != toupdate.end(); ++it) {
            auto [name, value] = *it;

            // Check if this field exists in current fields
            bool exists = false;
            iterator current_it(update_buffer_);
            for(; current_it.address() != current_it.end(); ++current_it) {
                if(current_it.name() == name) {
                    exists = true;
                    break;
                }
            }

            if(exists) {
                // Remove actual, then append.
                update_buffer_.erase(
                    (current_it.address() - update_buffer_.c_str()),
                    current_it.pair_size());
                append_field(update_buffer_, name, value);
            } else {
                // Add new field to update_buffer_
                append_field(update_buffer_, name, value);
                count++;
            }
        }

        // Step 3: Update count field in update_buffer_
        *reinterpret_cast<uint32_t *>(&update_buffer_[0]) = count;
        return Slice(update_buffer_.data(), update_buffer_.size());
    }

    template <typename Field_>
    void from_vector(const std::vector<Field_> &vec) {
        for(const Field_ &field : vec) {
            add(field.name, field.value);
        }
    }

    template <typename Field_> void to_vector(std::vector<Field_> &vec) {
        vec.clear();
        for(auto it = begin(); it != end(); ++it) {
            vec.emplace_back(
                Field_{it.name().ToString(), it.value().ToString()});
        }
    }

    template <typename Field_> std::vector<Field_> to_vector() {
        std::vector<Field_> vec;
        for(auto it = begin(); it != end(); ++it) {
            vec.emplace_back(
                Field_{it.name().ToString(), it.value().ToString()});
        }
        return vec;
    }

    // Get raw buffer for serialization
    const std::string &buffer() const { return buffer_; }

  private:
    static void append_field(std::string &buffer, const Slice &name,
                             const Slice &value) {
        uint32_t name_size = static_cast<uint32_t>(name.size());
        uint32_t value_size = static_cast<uint32_t>(value.size());

        size_t old_size = buffer.size();
        buffer.resize(old_size + 2 * sizeof(uint32_t) + name_size + value_size);
        char *ptr = &buffer[old_size];

        *reinterpret_cast<uint32_t *>(ptr) = name_size;
        ptr += sizeof(uint32_t);
        *reinterpret_cast<uint32_t *>(ptr) = value_size;
        ptr += sizeof(uint32_t);
        std::memcpy(ptr, name.data(), name_size);
        ptr += name_size;
        std::memcpy(ptr, value.data(), value_size);
    }

    std::string buffer_; // Contiguous buffer: [count:4][field1][field2]...
    std::string update_buffer_; // Temporary buffer for update operations
};

// Implementation of filter (needs Fields to be defined)
inline void
ReadonlyFields::filter(Fields &dest,
                       const std::unordered_set<std::string> &fields) const {
    dest.clear();

    if(fields.empty())
        return;

    // Iterate through all fields in this object
    for(auto it = begin(); it != end(); ++it) {
        auto [name, value] = *it;

        // Check if this field name is in the filter set
        // Convert Slice to string for comparison with unordered_set
        std::string name_str(name.data(), name.size());
        if(fields.find(name_str) != fields.end()) {
            // Add this field to destination
            dest.push(name, value);
        }
    }
};

} // namespace ycsbc

#endif // YCSB_C_FIELDS_H_
