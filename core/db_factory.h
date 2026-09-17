//
//  db_factory.h
//  YCSB-cpp
//
//  Copyright (c) 2020 Youngjae Lee <ls4154.lee@gmail.com>.
//  Copyright (c) 2014 Jinglei Ren <jinglei@ren.systems>.
//

#ifndef YCSB_C_DB_FACTORY_H_
#define YCSB_C_DB_FACTORY_H_

#include "db_database.h"
#include "measurements.h"
#include "utils/properties.h"

#include <string>
#include <map>

namespace ycsbc {

class DBFactory {
  public:
    // A storage-engine adapter implements the full row interface (DB).
    using DBCreator = DB *(*)();
    // A data-structure adapter implements only the primitive backend contract
    // (DBInterface); the factory wraps it in a RowStoreDB for the client.
    using DSCreator = DBInterface *(*)();

    static bool RegisterDB(std::string db_name, DBCreator db_creator);
    static bool RegisterDataStructure(std::string ds_name,
                                      DSCreator ds_creator);

    /// Creates a DB instance for the adapter named by the `dbname` property.
    /// Returns nullptr for an unknown name.
    static DB *CreateDB(utils::Properties *props, Measurements *measurements);

    /// True when `name` is registered as an in-memory data structure (which the
    /// runtime drives with a single instance and a single thread).
    static bool IsDataStructure(const std::string &name);

  private:
    static std::map<std::string, DBCreator> &DBRegistry();
    static std::map<std::string, DSCreator> &DSRegistry();
};

} // namespace ycsbc

#endif // YCSB_C_DB_FACTORY_H_
