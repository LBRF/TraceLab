/*

******************************************************************************************
						NOTES ON HOW TO USE AND MODIFY THIS FILE
******************************************************************************************

This file is used at the beginning of your project to create the SQLite database in which
all recorded experiment data is stored.

By default there are only two tables that KLibs writes data to: the 'participants' table,
which stores demograpic and runtime information, and the 'trials' table, which is where
the data recorded at the end of each trial is logged. You can also create your own tables
in the database to record data for things that might happen more than once a trial
(e.g eye movements) or only once a session (e.g. a questionnaire or quiz), or to log data
for recycled trials that otherwise wouldn't get written to the 'trials' table.


As your project develops, you may change the number of columns, add other tables, or
change the names/datatypes of columns that already exist.

To do this, modify this document as needed, then rebuild the project database by running:

  klibs db-rebuild

while within the root of your project folder.

But be warned: THIS WILL DELETE ALL YOUR CURRENT DATA. The database will be completely 
destroyed and rebuilt. If you wish to keep the data you currently have, run:

  klibs export

while within the root of your project folder. This will export all participant and trial
data in the database to text files found in TraceLab/ExpAssets/Data.


Note that you *really* do not need to be concerned about datatypes when adding columns;
in the end, everything will be a string when the data is exported. The *only* reason you
would use a datatype other than 'text' would be to ensure that the program will throw an
error if, for example, it tries to assign a string to a column you know is always going
to be an integer.

*/

CREATE TABLE participants (
	id                 INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	user_id            INTEGER                           NOT NULL UNIQUE,
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
	condition        TEXT                              NOT NULL,
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
	mt               FLOAT                             NOT NULL,
	armed_properly	 BOOLEAN						   NOT NULL
);

CREATE TABLE sessions (
	id             INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	participant_id INTEGER                           NOT NULL,
	user_id        TEXT                            	 NOT NULL,
	session_number INTEGER                           NOT NULL,
	completed      TEXT
);
