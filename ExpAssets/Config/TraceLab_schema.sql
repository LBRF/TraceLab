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
	id integer primary key autoincrement not null,
	userhash text not null unique,
	random_seed text not null,
	sex text not null,
	age integer not null,
	handedness text not null,
	created text not null,
	klibs_commit text not null,
	exp_condition integer,
	session_count integer,
	feedback_type text,
	sessions_completed integer,
  figure_set text
);


CREATE TABLE trials (
	id integer primary key autoincrement not null,
	participant_id integer key not null,
	block_num integer not null,
	session_num integer not null,
	condition text not null,
	trial_num integer not null,
	figure_type text not null, /* rehearsal figure vs random */
	figure_file text not null,
	stimulus_gt float not null, /* goal animation time */
	stimulus_mt float not null, /* real animation time */
	avg_velocity float not null,
	path_length float not null,
	trace_file text not null,
  rt  float not null,  /* initiation time for all conditions*/
  it  float not null,  /* time between RT and MT for physical conditions, ie. lingering at origin*/
	control_question text not null,
	control_response integer not null,
	mt float not null
);


CREATE TABLE events (
	id integer primary key autoincrement not null,
	user_id integer not null,
	trial_id integer not null,
	trial_num integer not null,
	label text not null,
	trial_clock float not null,
	eyelink_clock integer
);

CREATE TABLE logs (
	id integer primary key autoincrement not null,
	user_id integer not null,
	message text not null,
	trial_clock float not null,
	eyelink_clock integer
);


