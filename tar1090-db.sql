use crows_nest;

CREATE OR REPLACE TABLE tar1090_db(hex CHAR(6), registration VARCHAR(25), icao_type_code VARCHAR(4), name VARCHAR(75), PRIMARY KEY(hex));

LOAD DATA INFILE '/opt/crows_nest/tar1090-db.csv' INTO TABLE tar1090_db FIELDS TERMINATED BY ',';

