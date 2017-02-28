/*

******************************************************************************************
						NOTES ON HOW TO USE AND MODIFY THIS FILE
******************************************************************************************
This file is used at the beginning of your project to create the database in 
which trials and participants are stored.

As the project develops, you may change the number of columns, add other tables,
or change the names/datatypes of columns that already exist.

That said,  You *really* do not need to be concerned about datatypes; in the end, everything will be a string when the data
is output. The *only* reason to change the datatypes here are to ensure that the program will throw an error if, for
example, a string is returned for something like reaction time. BUT, you should be catching this in your experiment.py
file; if the error is caught here it means you've already been collecting the wrong information and it should have
been caught much earlier.

To do this, modify the document as needed, then, in your project. To rebuild the database with
your changes just delete your database files, or just run:

  rm /Users/jono/Documents/Clients//TraceLab/ExpAssets/TraceLab.db*

and run the experiment, this will force klibs to rebuild your database.

But be warned: THIS WILL DELETE ALL YOUR CURRENT DATA. The database will be completely 
destroyed and rebuilt. If you wish to keep the data you currently have, be sure to first run:

  klibs export /Users/jono/Documents/Clients//TraceLab

This wil export the database in it's current state to text files found in /Users/jono/Documents/Clients//Data.

*/

CREATE TABLE participants (
	id                 INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	user_id            TEXT                              NOT NULL UNIQUE,
	random_seed        TEXT                              NOT NULL,
	sex                TEXT                              NOT NULL,
	age                INTEGER                           NOT NULL,
	handedness         TEXT                              NOT NULL,
	klibs_commit       TEXT                              NOT NULL,
	exp_condition      INTEGER,
	session_count      INTEGER,
	feedback_type      TEXT,
	sessions_completed INTEGER DEFAULT 0,
	figure_set         TEXT DEFAULT 'NA',
	created            TEXT                              NOT NULL,
	initialized        INTEGER DEFAULT 0
);

CREATE TABLE trials (
	id               INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	participant_id   INTEGER                           NOT NULL,
	block_num        INTEGER                           NOT NULL,
	session_num      INTEGER                           NOT NULL,
	exp_condition    TEXT                              NOT NULL,
	trial_num        INTEGER                           NOT NULL,
	figure_type      TEXT                              NOT NULL,
	figure_file      TEXT                              NOT NULL,
	stimulus_gt      FLOAT                             NOT NULL,
	stimulus_mt      FLOAT                             NOT NULL,
	avg_velocity     FLOAT                             NOT NULL,
	path_length      FLOAT                             NOT NULL,
	trace_file       TEXT                              NOT NULL,
	rt               FLOAT                             NOT NULL,
	it               FLOAT                             NOT NULL,
	control_question TEXT                              NOT NULL,
	control_response INTEGER                           NOT NULL,
	mt               FLOAT                             NOT NULL
);

CREATE TABLE sessions (
	id             INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	participant_id INTEGER                           NOT NULL,
	session_number INTEGER                           NOT NULL,
	completed      TEXT
);


CREATE TABLE events (
	id            INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	user_id       INTEGER                           NOT NULL,
	trial_id      INTEGER                           NOT NULL,
	trial_num     INTEGER                           NOT NULL,
	label         TEXT                              NOT NULL,
	trial_clock   FLOAT                             NOT NULL,
	eyelink_clock INTEGER
);

CREATE TABLE logs (
	id            INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	user_id       INTEGER                           NOT NULL,
	message       TEXT                              NOT NULL,
	trial_clock   FLOAT                             NOT NULL,
	eyelink_clock INTEGER
);


