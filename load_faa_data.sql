
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
