__author__ = 'jono'

"""
NOTE: this entire document only exists because experiment.previous.py was getting too cluttered
and I decided to relocate all session-init logic to a separate class to tidy things up. previous
versions of the experiment all included these methods as part of the experiment class
"""

import os
import io
import sys
import shutil

from klibs import P
from klibs.KLInternal import load_source
from klibs.KLEnvironment import EnvAgent
from klibs.KLJSON_Object import AttributeDict
from klibs.KLUtilities import now, utf8
from klibs.KLRuntimeInfo import runtime_info_init
from klibs.KLStructure import FactorSet
from klibs.KLTrialFactory import TrialIterator
from klibs.KLUserInterface import any_key
from klibs.KLDatabase import EntryTemplate
from klibs.KLGraphics import blit, flip, fill
from klibs.KLCommunication import query, message, collect_demographics
from klibs.KLCommunication import user_queries as uq

from utils import get_hostname


PHYS = "physical"
MOTR = "imagery"
CTRL = "control"
FB_DRAW = "drawing_feedback"
FB_RES = "results_feedback"
FB_ALL = "all_feedback"



class TraceLabSession(EnvAgent):

	def __init__(self):

		self.user_id = None
		self.__verify_session_structures()
		if P.use_figure_sets:
			self.validate_figure_sets()

		incomplete = self.db.select('participants', ['id', 'user_id'], where={'initialized': 0})
		if len(incomplete):
			if query(uq.experimental[5]) == "p":
				self.__purge_incomplete(incomplete)
			else:
				self.__report_incomplete(incomplete)

		if P.development_mode:
			# Write data to subfolder when in development mode to avoid cluttering
			# data directory with non-participant data
			devmode_data_dir = os.path.join(P.data_dir, "devmode")
			if not os.path.exists(devmode_data_dir):
				os.makedirs(devmode_data_dir)
			P.data_dir = devmode_data_dir
			self.user_id = self.create_new_user()
		else:
			self.user_id = self.get_user_id()

		P.demographics_collected = True
		self.restore_session(self.user_id)
		self.init_session()
		self.create_session_dirs()


	def __report_incomplete(self, participant_ids):

		log_path = os.path.join(P.local_dir, "uninitialized_users_{0}".format(now(True)))
		log = io.open(log_path, "w+", encoding='utf-8')
		p_cols = [
			'user_id', 'session_structure', 'session_count', 'sessions_completed',
			'figure_set', 'handedness', 'created'
		]
		header = p_cols + ["session_rows", "trial_rows"]
		log.write("\t".join(header))
		for p in participant_ids:
			data = self.db.select('participants', p_cols, where={'id': p[0]})[0]
			num_sessions = len(self.db.select('sessions', ['id'], where={'participant_id': p[0]}))
			num_trials = len(self.db.select('trials', ['id'], where={'participant_id': p[0]}))
			data += [num_sessions, num_trials]
			log.write("\n")
			log.write("\t".join([utf8(i) for i in data]))
		log.close()
		self.exp.quit()


	def __purge_incomplete(self, participant_ids):

		for p in participant_ids:
			self.db.delete(table='participants', where={'id': p[0]})
			self.db.delete(table='sessions', where={'participant_id': p[0]})
			self.db.delete(table='trials', where={'participant_id': p[0]})

		self.db.commit()


	def __verify_session_structures(self):

		error_strings = {
			"bad_format": "Response type and feedback type must be separated by a single hyphen.",
			"bad_condition": ("Response type must be either 'PP' (physical), 'MI' (imagery), "
				"or 'CC' (control)."),
			"bad_feedback": ("Feedback type must be one or two characters long, and be "
				"a combination of the letters 'V', 'R' and / or 'X'."),
			"bad_trialcount": ("Custom trial counts must be specified in (blocktype, trials) "
				"format, where 'trials' is a positive integer."),
		}

		# Validate specified session structure to use, return informative error if formatted wrong
		session_num, block_num = (0, 0)
		e = "Error encountered parsing Block {0} of Session {1} in session structure '{2}' ({3}):"
		for structure_key, session_structure in P.session_structures.items():
			for session in session_structure:
				session_num += 1
				for block in session:
					block_num += 1
					if type(block) in [tuple, list]:
						if isinstance(block[1], int) and block[1] > 0:
							err = self.validate_block_condition(block[0])
						else:
							err = "bad_trialcount"
					else:
						err = self.validate_block_condition(block)
					if err:
						if isinstance(block, tuple):
							block = list(block)
						err_txt1 = e.format(block_num, session_num, structure_key, str(block))
						err_txt1 += "\n" + error_strings[err]
						msg1 = message(err_txt1, "error", align="center")
						msg2 = message("Press any key to exit TraceLab.")
						fill()
						blit(msg1, 2, (P.screen_c[0], P.screen_c[1] - 30))
						blit(msg2, 8, P.screen_c)
						flip()
						any_key()
						self.exp.quit()


	def validate_figure_sets(self):

		err_txt = (
			"The figure '{0}' in figure set '{1}' does not exist in the task's "
			"figures folder. Please check that the name is correct."
		)

		# Validate figure sets for project
		for name, values in P.figure_sets.items():
			# Validate that it works correctly as a factor override
			tmp = FactorSet({'figure_name': values})
			# Ensure all named figures actually exist
			for f in tmp._factors['figure_name']:
				figfile = f + ".tlf"
				f_path = os.path.join(P.resources_dir, "figures", f, figfile)
				if not os.path.exists(f_path) and f != "random":
					raise RuntimeError(err_txt.format(f, name))


	def create_new_user(self):

		# If multiple possible session structures, query user to choose which one to use
		structure_names = list(P.session_structures.keys())
		if len(structure_names) > 1:
			# Since this needs to match one of the keys of P.session_structures, we create the
			# query object directly here instead of in the user_queries file so we can set
			# 'accepted' to 'structure_names'
			cond_q = AttributeDict({
			    "title": "session_structure",
			    "query": "Please enter the name of the session structure to use:",
			    "accepted": structure_names,
			    "allow_null": False,
			    "format": AttributeDict({
			        "type": "str",
			        "styles": "default",
			        "positions": "default",
			        "password": False,
			        "case_sensitive": True,
			        "action": None
			    })
			})
			structure_key = query(cond_q)
		else:
			structure_key = structure_names[0]
		P.blocks_per_experiment = len(P.session_structures[structure_key][0])

		# Query user whether they want to select a figure set by name for the participant
		figure_set_name = "NA"
		if P.use_figure_sets:
			figure_set_name = self.__get_figure_set_name()

		# Collect user demographics and retrieve user id from database
		collect_demographics(P.development_mode)
		user_id = self.db.select('participants', ['user_id'], where={'id': P.p_id})[0][0]

		# Update participant info table with session and figure set info
		info = {
			'session_structure': structure_key,
			'session_count': len(P.session_structures[structure_key]),
			'figure_set': figure_set_name,
			'initialized': 1,
		}
		self.db.update('participants', info)

		return user_id


	def get_participant_info(self, user_id):
		# Retrieve all participant info as a dict
		cols = self.db.get_columns('participants')
		rows = self.db.select('participants', where={'user_id': user_id})
		# If participant matching identifier exists, return dict with data
		if len(rows):
			out = {}
			for i in range(len(cols)):
				out[cols[i]] = rows[0][i]
			return out
		# If no matching participant, return None
		return None


	def get_user_id(self):
		user_id = None
		while not user_id:
			user_id = query(uq.experimental[1])
			# If ID provided, see if it exists 
			if user_id:
				info = self.get_participant_info(user_id)
				if not info:
					user_id = None
					# If ID doesn't exist and user declines to try another, exit
					if query(uq.experimental[0]) == "n":
						fill()
						msg = message("Thanks for participating!", "default")
						blit(msg, 5, P.screen_c)
						flip()
						any_key()
						self.exp.quit()
			# If no ID provided, create a new one
			else:
				user_id = self.create_new_user()
	
		return user_id


	def __check_incomplete_session(self):

		start_block = 1
		start_trial = 1
		existing = {'participant_id': P.participant_id, 'session_num': self.exp.session_number}
		partial_session = self.db.select('trials', ['block_num'], existing)
		if len(partial_session):
			partial_q = AttributeDict({
			    "title": "partial session prompt",
			    "query": (
					"This participant did not complete all trials of the previous session. "
					"Would you like to:\n"
					"(r)edo the last session, (c)ontinue from the end of the last completed trial, "
					"or (a)dvance to the next session?"
				),
			    "accepted": ['r', 'c', 'a'],
			    "allow_null": False,
			    "format": AttributeDict({
			        "type": "str",
			        "styles": "default",
			        "positions": "default",
			        "password": False,
			        "case_sensitive": False,
			        "action": None
			    })
			})
			resp = query(partial_q)
			if resp == "r":
				self.db.delete('trials', existing) # remove database data
				shutil.rmtree(self.exp.fig_dir) # remove figure data
			elif resp == "c":
				# If resuming from end of last finished trial, first get last block in db for
				# this participant + session, then figure out if it was completed or not
				max_block = max([num[0] for num in partial_session])
				existing['block_num'] = max_block
				prev_trials = self.db.select('trials', ['trial_num'], existing)
				max_trial = max([num[0] for num in prev_trials])
				start_block = max_block + 1 if max_trial == P.trials_per_block else max_block
				start_trial = max_trial + 1 if max_trial < P.trials_per_block else 1
			elif resp == "a":
				new_session_dir = "session_" + str(self.exp.session_number + 1)
				self.exp.fig_dir = os.path.join(self.exp.p_dir, new_session_dir)
				self.db.update('participants', {'sessions_completed': self.exp.session_number})
				self.exp.session_number += 1

		return (start_block, start_trial)


	def __get_figure_set_name(self):

		figset_q = AttributeDict({
		    "title": "figureset name",
		    "query": "Please enter the name of the figure set to use:",
		    "accepted": P.figure_sets.keys(),
		    "allow_null": False,
		    "format": AttributeDict({
		        "type": "str",
		        "styles": "default",
		        "positions": "default",
		        "password": False,
		        "case_sensitive": True,
		        "action": None
		    })
		})

		return query(figset_q)


	def __generate_blocks(self, current_session):
		"""Generates the full set of trials for each block in the session.
		
		This generates each block separately, ensuring a full set of factors in
		each block and handling blocks with custom trial counts.

		"""
		blocks = []
		exp_factors = self.exp.trial_factory.exp_factors
		for block in current_session:
			trials = P.trials_per_block
			if type(block) in [tuple, list]:
				trials = block[1]
				block = block[0]
			blocks += self.exp.trial_factory.trial_generator(exp_factors, 1, trials)

		return blocks


	def create_session_dirs(self):

		# Initialize figure paths for current participant/session
		date = self.exp.created.split("_")[0]
		p_dir = "p{0}_{1}".format(P.participant_id, date)
		if P.append_hostname:
			hostname = get_hostname()
			p_dir += "-{0}".format(hostname)
		session_dir = "session_" + str(self.exp.session_number)
		self.exp.p_dir = os.path.join(P.data_dir, p_dir)
		self.exp.fig_dir = os.path.join(self.exp.p_dir, session_dir)

		# If needed, create figure folder for session
		if not os.path.exists(self.exp.fig_dir):
			os.makedirs(self.exp.fig_dir)


	def init_session(self):

		# If any existing trial data for this session+participant, prompt experimenter whether to
		# delete existing data and redo session, continue from start of last completed block,
		# or continue to next session
		start_block, start_trial = self.__check_incomplete_session()

		# Load session structure. If participant already completed all sessions, show message
		# and quit.
		session_structure = P.session_structures[self.exp.session_structure]
		num_sessions = len(session_structure)
		if self.exp.session_number > num_sessions:
			txt1 = "Participant {0} has already completed all {1} sessions of the task."
			msg1 = message(txt1.format(self.user_id, num_sessions))
			msg2 = message("Press any key to exit TraceLab.")
			fill()
			blit(msg1, 2, (P.screen_c[0], P.screen_c[1] - 30))
			blit(msg2, 8, P.screen_c)
			flip()
			any_key()
			self.exp.quit()

		# Parse block strings for current session
		current_session = session_structure[self.exp.session_number - 1]
		P.blocks_per_experiment = len(current_session)
		for block in current_session:
			cond = block if isinstance(block, str) else block[0]
			resp, fb = self.parse_exp_condition(cond)
			self.exp.block_factors.append({'response_type': resp, 'feedback_type': fb})

		# Generate trials and import the figure set specified earlier
		if self.exp.figure_set_name != "NA":
			self.apply_figure_set(self.exp.figure_set_name)
		blocks = self.__generate_blocks(current_session)
		self.exp.blocks = [TrialIterator(b) for b in blocks]
		self.exp.trial_factory.blocks = self.exp.blocks
		self.exp.trial_factory.dump()

		# If resuming incomplete session, skip ahead to last completed trial
		if start_block > 1 or start_trial > 1:
			blocks = blocks[(start_block - 1): ] # Drop completed blocks
			blocks[0] = blocks[0][(start_trial - 1): ] # Drop completed trials
			self.exp.blocks = [TrialIterator(b) for b in blocks]

		# If session number > 1, log runtime info for session in runtime_info table
		if 'session_info' in self.db.table_schemas.keys() and self.exp.session_number > 1:
			runtime_info = EntryTemplate('session_info')
			for col, value in runtime_info_init().items():
				if col == 'session_number':
					value = self.exp.session_number
				runtime_info.log(col, value)
			self.db.insert(runtime_info)


	def restore_session(self, user_id):

		# Reload participant data from database into experiment variables
		info = self.get_participant_info(user_id)
		P.participant_id = info['id']
		self.exp.session_structure = info['session_structure']
		self.exp.session_count = info['session_count']
		self.exp.session_number = info['sessions_completed'] + 1
		self.exp.figure_set_name = info['figure_set']
		self.exp.handedness = info['handedness']
		self.exp.created = info['created']
		P.session_number = self.exp.session_number


	def apply_figure_set(self, figure_set):

		# If reloading a participant, make sure figure set still exists
		if not figure_set in P.figure_sets.keys():
			e = ("Unable to reload participant initialized with figure set '{}', "
				 "which no longer exists!")
			raise RuntimeError(e.format(figure_set))

		# Overwrite 'figure_name' trial factor with values defined in chosen figure set
		tmp = FactorSet({
			'figure_name': P.figure_sets[figure_set]
		})
		self.exp._exp_factors['figure_name'] = tmp._factors['figure_name']
		self.exp.trial_factory.exp_factors['figure_name'] = tmp._factors['figure_name']


	def validate_block_condition(self, condition):

		err_type = None
		args = condition.split("-")
		if len(args) != 2:
			err_type = "bad_format"
		else:
			response, feedback = args
			# Validate feedback format
			feedback = list(feedback)
			for i in feedback:
				if i not in ["V", "R", "X"] or len(feedback) > 2:
					err_type = "bad_feedback"
			# Validate condition format
			if response not in ["PP", "MI", "CC"]:
				err_type = "bad_condition"

		return err_type


	def parse_exp_condition(self, condition):

		response, feedback = condition.split("-")

		resp_map = {'PP': PHYS, 'MI': MOTR, 'CC': CTRL}
		resp = resp_map[response]

		if "V" in feedback and "R" in feedback:
			fb = FB_ALL
		elif "R" in feedback:
			fb = FB_RES
		elif "V" in feedback:
			fb = FB_DRAW
		else:
			fb = "False"

		return [resp, fb]
