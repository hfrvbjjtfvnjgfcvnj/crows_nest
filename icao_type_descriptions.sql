use crows_nest;

CREATE OR REPLACE TABLE icao_type_descriptions (type VARCHAR(4), description CHAR(3), PRIMARY KEY(type));
LOAD DATA INFILE '/opt/crows_nest/icao_type_descriptions.csv' INTO TABLE icao_type_descriptions FIELDS TERMINATED BY ',';
