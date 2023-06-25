--CREATE DATABASE crows_nest;

use crows_nest;
-- log of all messages
CREATE OR REPLACE TABLE data_log (
	time DOUBLE, 
	hex CHAR(6), 
	flight varchar(16), 
	lat FLOAT, 
	lon FLOAT, 
	altitude INT, 
	vert_rate INT,
	track INT,
	speed INT,
	seen FLOAT,
	seen_pos FLOAT,
	rssi FLOAT,
	nucp INT,
	category char(2) DEFAULT "",
	squawk char(4) DEFAULT "",

	PRIMARY KEY(time, hex)
);

-- FAA aircraft registration master table 
CREATE OR REPLACE TABLE faa_master(
	n_number varchar(5) PRIMARY KEY, 
	serial_number varchar(30), 
	aircraft_mfr_model_code varchar(7),
	engine_mfr_model_code varchar(5),
	year_mfr varchar(4),
	type_of_registrant char(1),
	registrant_name varchar(50),
	reg_street1 varchar(33) DEFAULT "",
	reg_street2 varchar(33) DEFAULT "",
	reg_city varchar(18),
	reg_state char(2),
	reg_zip varchar(10),
	reg_region char(1),
	reg_county_mail varchar(3),
	reg_country_mail varchar(2),
	last_activity_date char(8),
	cert_issue_date char(8),
	certification_codes varchar(10),
	type_aircraft char(1),
	type_engine int,
	status_code varchar(2),
	mode_s_code varchar(8),
	fractional_ownership varchar(1) DEFAULT "",
	airworthiness_date char(8),
	other_name_1 varchar(50) DEFAULT "",
        other_name_2 varchar(50) DEFAULT "",
        other_name_3 varchar(50) DEFAULT "",
        other_name_4 varchar(50) DEFAULT "",
        other_name_5 varchar(50) DEFAULT "",
        expiration_date char(8),
        unique_id varchar(8),
        kit_mfr varchar(30) DEFAULT "",
        kit_model varchar(20) DEFAULT "",
        mode_s_hex_code varchar(10)
);
LOAD DATA INFILE '/opt/crows_nest/MASTER.txt' INTO TABLE faa_master FIELDS TERMINATED BY ',' IGNORE 1 LINES;

-- maps ICAO hex to N-number (there's an algorithm to do this, but I didn't know that at the time, so we cache the ones we know)
CREATE OR REPLACE TABLE faa_lookup_table(mode_s_hex_code char(6) PRIMARY KEY, n_number varchar(5), type_aircraft char(1)) as select mode_s_hex_code,n_number,type_aircraft from faa_master;

-- FAA registration records associated with a 'government entity' - see parser code for futher details
CREATE OR REPLACE TABLE gov_records (hex char(5) PRIMARY KEY,org varchar(128));
LOAD DATA INFILE '/opt/crows_nest/GOVT_RECORDS.txt' INTO TABLE gov_records FIELDS TERMINATED BY ',';

-- FAA registration records associated with a 'military entity' - see parser code for futher details
CREATE OR REPLACE TABLE mil_records (hex char(5) PRIMARY KEY,org varchar(128));
LOAD DATA INFILE '/opt/crows_nest/MIL_RECORDS.txt' INTO TABLE mil_records FIELDS TERMINATED BY ',';

-- ICAO official type descriptions
CREATE OR REPLACE TABLE icao_type_descriptions (type VARCHAR(4), description CHAR(3), PRIMARY KEY(type));
LOAD DATA INFILE '/opt/crows_nest/icao_type_descriptions.csv' INTO TABLE icao_type_descriptions FIELDS TERMINATED BY ',';

-- signal reception records - used to generate a beam pattern/reception horizon
CREATE OR REPLACE TABLE signal_reception(id INT NOT NULL AUTO_INCREMENT, time DOUBLE, bearing SMALLINT, dist FLOAT, alt INT, rssi FLOAT, PRIMARY KEY(id));

-- flags to denote a type of alert on an aircraft
CREATE OR REPLACE TABLE alert_type(id INT PRIMARY KEY, name varchar(15));
delete from alert_type;
insert into alert_type(id,name) values(0,"special");
insert into alert_type(id,name) values(1,"spook");
insert into alert_type(id,name) values(2,"interesting");
insert into alert_type(id,name) values(3,"loiter");
insert into alert_type(id,name) values(4,"intercept");
insert into alert_type(id,name) values(5, "eta");
insert into alert_type(id,name) values(6,"local");
insert into alert_type(id,name) values(7,"state");
insert into alert_type(id,name) values(8,"federal");
insert into alert_type(id,name) values(9,"military");
insert into alert_type(id,name) values(10,"government");
insert into alert_type(id,name) values(11,"other");

-- official FAA registration aircraft types
CREATE OR REPLACE TABLE faa_aircraft_type(id CHAR, name varchar(30));
insert into faa_aircraft_type(id,name) values ('1',"glider");
insert into faa_aircraft_type(id,name) values ('2',"balloon");
insert into faa_aircraft_type(id,name) values ('3',"blimp/dirigible");
insert into faa_aircraft_type(id,name) values ('4',"fixed wing - single engine");
insert into faa_aircraft_type(id,name) values ('5',"fixed wing - multi engine");
insert into faa_aircraft_type(id,name) values ('6',"rotorcraft");
insert into faa_aircraft_type(id,name) values ('7',"weight-shift-control");
insert into faa_aircraft_type(id,name) values ('8',"powered parachute");
insert into faa_aircraft_type(id,name) values ('9',"gyroplane");
insert into faa_aircraft_type(id,name) values ('H',"hybrid lift");
insert into faa_aircraft_type(id,name) values ('O',"other");

-- table of aircraft actively being tracked
CREATE OR REPLACE TABLE active_aircraft(hex CHAR(6), time DOUBLE, seen_pos FLOAT, latitude DOUBLE, longitude DOUBLE, distance FLOAT, bearing INT, first_det_time DOUBLE, speed INT, track INT, altitude INT, PRIMARY KEY(hex));

-- table history of positions of aircraft actively being tracked
CREATE OR REPLACE TABLE active_aircraft_history(hex CHAR(6), time DOUBLE, seen_pos FLOAT, latitude DOUBLE, longitude DOUBLE, distance FLOAT, bearing INT, speed INT, track INT, altitude INT, PRIMARY KEY(hex,time));

-- list of aircraft we have ever tracked
CREATE OR REPLACE TABLE detected_aircraft(hex CHAR(6), time DOUBLE, seen_pos FLOAT, PRIMARY KEY(hex));

-- list of aircraft for which we have published alerts
CREATE OR REPLACE TABLE active_alerts(hex CHAR(6), first_seen DOUBLE, last_seen DOUBLE, alert_type INT, PRIMARY KEY(hex));

-- list of "special" aircraft to alert for (ex: so-and-so's private jet N00000)
CREATE OR REPLACE TABLE special_aircraft(hex CHAR(6) PRIMARY KEY, alert_type INT);

-- table of type reference data from tar1090 database (most useful for foreign or military aircraft)
CREATE OR REPLACE TABLE tar1090_db(hex CHAR(6), registration VARCHAR(25), icao_type_code VARCHAR(4), name VARCHAR(75), PRIMARY KEY(hex));
LOAD DATA INFILE '/opt/crows_nest/tar1090-db.csv' INTO TABLE tar1090_db FIELDS TERMINATED BY ',';

-- list of labels we find 'interesting'
CREATE OR REPLACE TABLE interesting_labels(label varchar(50) PRIMARY KEY NOT NULL);
LOAD DATA INFILE '/opt/crows_nest/interesting_labels.csv' INTO TABLE interesting_labels FIELDS TERMINATED BY ',';

-- list of labels we find 'spooky'
CREATE OR REPLACE TABLE spooky_labels(label varchar(50) PRIMARY KEY NOT NULL);
LOAD DATA INFILE '/opt/crows_nest/spooky_labels.csv' INTO TABLE spooky_labels FIELDS TERMINATED BY ',';

-- list of opeartors to ignore
CREATE OR REPLACE TABLE ignore_registrants(registrant_name varchar(50) PRIMARY KEY NOT NULL);
