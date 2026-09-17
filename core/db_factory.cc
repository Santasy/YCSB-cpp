//
//  db_factory.cc
//  YCSB-cpp
//
//  Copyright (c) 2020 Youngjae Lee <ls4154.lee@gmail.com>.
//  Copyright (c) 2014 Jinglei Ren <jinglei@ren.systems>.
//

#include "db_factory.h"
#include "basic_db.h"
#include "db_wrapper.h"

namespace ycsbc {

std::map<std::string, DBFactory::DBCreator> &DBFactory::DBRegistry() {
    static std::map<std::string, DBCreator> registry;
    return registry;
}

std::map<std::string, DBFactory::DSCreator> &DBFactory::DSRegistry() {
    static std::map<std::string, DSCreator> registry;
    return registry;
}

bool DBFactory::RegisterDB(std::string db_name, DBCreator db_creator) {
    DBRegistry()[db_name] = db_creator;
    return true;
}

bool DBFactory::RegisterDataStructure(std::string ds_name,
                                      DSCreator ds_creator) {
    DSRegistry()[ds_name] = ds_creator;
    return true;
}

DB *DBFactory::CreateDB(utils::Properties *props, Measurements *measurements) {
    std::string db_name = props->GetProperty("dbname", "basic");
    DB *db = nullptr;
    std::map<std::string, DBCreator> &db_registry = DBRegistry();
    std::map<std::string, DSCreator> &ds_registry = DSRegistry();
    if(db_registry.find(db_name) != db_registry.end()) {
        DB *new_db = (*db_registry[db_name])();
        new_db->SetProps(props);
        db = new DBWrapper(new_db, measurements);
    } else if(ds_registry.find(db_name) != ds_registry.end()) {
        // Data structures implement the raw contract only; lift them to the row
        // interface so the client hot loop is backend-agnostic.
        DBInterface *store = (*ds_registry[db_name])();
        store->SetProps(props);
        db = new DBWrapper(new RowStoreDB(store), measurements);
    }
    return db;
}

bool DBFactory::IsDataStructure(const std::string &name) {
    std::map<std::string, DSCreator> &ds_registry = DSRegistry();
    return ds_registry.find(name) != ds_registry.end();
}

} // namespace ycsbc
