__author__ = 'jono'

"""
NOTE: this entire document only exists because experiment.previous.py was getting too cluttered and I decided to
relocate all session-init logic to a separate class to tidy things up. previous versions of the experiment
all included these methods as part of the experiment class
"""

import os
import sys
from imp import load_source
from shutil import rmtree

from klibs.KLConstants import QUERY_UPD, NA
from klibs import P
from klibs.KLEnvironment import EnvAgent
from klibs.KLJSON_Object import AttributeDict
from klibs.KLUtilities import now
from klibs.KLIndependentVariable import IndependentVariableSet
from klibs.KLRuntimeInfo import runtime_info_init
from klibs.KLUserInterface import any_key
from klibs.KLDatabase import EntryTemplate
from klibs.KLGraphics import blit, flip, fill
from klibs.KLCommunication import query, message, collect_demographics
from klibs.KLCommunication import user_queries as uq

from TraceLabFigure import TraceLabFigure
from FigureSet import FigureSet


PHYS = "physical"
MOTR = "imagery"
CTRL = "control"
FB_DRAW = "drawing_feedback"
FB_RES = "results_feedback"
FB_ALL = "all_feedback"



class TraceLabSession(EnvAgent):

	queries = {
		"user_data": "SELECT `id`,`random_seed`,`session_structure`, `session_count`, `sessions_completed`, `figure_set`, `handedness`,`created` FROM `participants` WHERE `user_id` = ?",
		"user_row": "SELECT `user_id`,`random_seed`,`session_structure`, `session_count`, `sessions_completed`, `figure_set`, `handedness`,`created` FROM `participants` WHERE `id` = ?",
		"get_user_id": "SELECT `user_id` FROM `participants` WHERE `id` = ?",
		"delete_anon": "DELETE FROM `trials` WHERE `participant_id` = ? AND `session_num` = ?",
		"delete_incomplete_user": "DELETE FROM `participants` WHERE `id` = ?",
		"delete_incomplete_user_sessions": "DELETE FROM `sessions` WHERE `participant_id` = ?",
		"delete_incomplete_user_trials": "DELETE FROM `trials` WHERE `participant_id` = ?",
		"find_incomplete": "SELECT `id`, `user_id`, `created` FROM `participants` WHERE `initialized` = 0",
		"completed_sessions": "SELECT * FROM `sessions` WHERE `participant_id` = ?",
		"completed_trials": "SELECT * FROM `trials` WHERE `participant_id` = ?"
	}


	def __init__(self):

		self.__user_id__ = None
		self.__verify_session_structures()
		self.__import_figure_sets()

		incomplete_participants = self.db.query(self.queries["find_incomplete"])
		if len(incomplete_participants):
			if query(uq.experimental[7]) == "p":
				self.__purge_incomplete(incomplete_participants)
			else:
				self.__report_incomplete(incomplete_participants)

		if P.development_mode:
			# Write data to subfolder when in development mode to avoid cluttering
			# data directory with non-participant data
			devmode_data_dir = os.path.join(P.data_dir, "devmode")
			if not os.path.exists(devmode_data_dir):
				os.makedirs(devmode_data_dir)
			P.data_dir = devmode_data_dir
		else:
			self.user_id = query(uq.experimental[1])
		if self.user_id is None:
			self.__generate_user_id()
		
		self.init_session()


	def __report_incomplete(self, participant_ids):

		log = open(os.path.join(P.local_dir, "uninitialized_users_{0}".format(now(True))), "w+")
		header = [
			"user_id", "random_seed", "exp_condition", "feedback_type", "session_count",
			"sessions_completed", "figure_set", "handedness","created", "session_rows", "trial_rows"
		]
		log.write("\t".join(header))
		for p in participant_ids:
			log.write("\n")
			p_data = self.db.query(self.queries['user_row'], q_vars=[p[0]])[0]
			p_data.append(len(self.db.query(self.queries['completed_sessions'], q_vars=[p[0]])))
			p_data.append(len(self.db.query(self.queries['completed_trials'], q_vars=[p[0]])))
			log.write("\t".join([str(i) for i in p_data]))
		log.close()
		self.exp.quit()


	def __purge_incomplete(self, participant_ids):

		for p in participant_ids:
			self.db.query(self.queries["delete_incomplete_user"], q_vars=[p[0]])
			self.db.query(self.queries["delete_incomplete_user_sessions"], q_vars=[p[0]])
			self.db.query(self.queries["delete_incomplete_user_trials"], q_vars=[p[0]])

			try:
				rmtree(os.path.join(P.data_dir, "{0}_{1}".format(*p[1:])))
			except OSError:
				pass

		self.db.commit()


	def __verify_session_structures(self):

		error_strings = {
			"bad_format": "Response type and feedback type must be separated by a single hyphen.",
			"bad_condition": ("Response type must be either 'PP' (physical), 'MI' (imagery), "
				"or 'CC' (control)."),
			"bad_feedback": ("Feedback type must be one or two characters long, and be "
				"a combination of the letters 'V', 'R' and / or 'X'.")
		}

		# Validate specified session structure to use, return informative error if formatted wrong
		session_num, block_num = (0, 0)
		e = "Error encountered parsing Block {0} of Session {1} in session structure '{2}' ({3}):"
		for structure_key, session_structure in P.session_structures.items():
			for session in session_structure:
				session_num += 1
				for block in session:
					block_num += 1
					err = self.validate_block_condition(block)
					if err:
						err_txt1 = e.format(block_num, session_num, structure_key, block)
						err_txt1 += "\n" + error_strings[err]
						msg1 = message(err_txt1, "error", align="center", blit_txt=False)
						msg2 = message("Press any key to exit TraceLab.", blit_txt=False)
						fill()
						blit(msg1, 2, (P.screen_c[0], P.screen_c[1] - 30))
						blit(msg2, 8, P.screen_c)
						flip()
						any_key()
						self.exp.quit()


	def __import_figure_sets(self):

		# load original complete set of FigureSets for use
		fig_sets_f = os.path.join(P.config_dir, "figure_sets.py")
		fig_sets_local_f = os.path.join(P.local_dir, "figure_sets.py")
		try:
			sys.path.append(fig_sets_local_f)
			for k, v in load_source("*", fig_sets_local_f).__dict__.items():
				if isinstance(v, FigureSet):
					self.exp.figure_sets[v.name] = v
			if P.dm_ignore_local_overrides:
				raise RuntimeError("ignoring local files")
		except (IOError, RuntimeError):
			sys.path.append(fig_sets_f)
			for k, v in load_source("*", fig_sets_f).__dict__.items():
				if isinstance(v, FigureSet):
					self.exp.figure_sets[v.name] = v


	def __generate_user_id(self):

		# If multiple possible session structures, query user to choose which one to use
		structure_names = P.session_structures.keys()
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
		if query(uq.experimental[3]) == "y":
			self.exp.figure_set_name = self.__get_figure_set_name()

		# Collect user demographics and retrieve user id from database
		collect_demographics(P.development_mode)
		self.user_id = self.db.query(self.queries["get_user_id"], q_vars=[P.p_id])[0][0]

		# Update participant info table with session and figure set info
		info = {
			'session_structure': structure_key,
			'session_count': len(P.session_structures[structure_key]),
			'figure_set': self.exp.figure_set_name
		}
		self.db.update('participants', info)


	def __get_figure_set_name(self):

		name = query(uq.experimental[4])
		if not name in self.exp.figure_sets:
			if query(uq.experimental[0]) == "y":
				return self.__get_figure_set_name()
			else:
				name = "NA"

		return name


	def init_session(self):

		try:
			user_data = self.db.query(self.queries['user_data'], q_vars=[self.user_id])[0]
			self.restore_session(user_data)
		except IndexError as e:
			if query(uq.experimental[0]) == "y":
				self.user_id = query(uq.experimental[1])
				if self.user_id is None:
					self.__generate_user_id()
				return self.init_session()
			else:
				fill()
				msg = message("Thanks for participating!", "default", blit_txt=False)
				blit(msg, 5, P.screen_c)
				flip()
				any_key()
				self.exp.quit()

		# Load session structure. If participant already completed all sessions, show message
		# and quit.
		session_structure = P.session_structures[self.exp.session_structure]
		num_sessions = len(session_structure)
		if self.exp.session_number > num_sessions:
			txt1 = "Participant {0} has already completed all {1} sessions of the task."
			msg1 = message(txt1.format(self.user_id, num_sessions), blit_txt=False)
			msg2 = message("Press any key to exit TraceLab.", blit_txt=False)
			blit(msg1, 2, (P.screen_c[0], P.screen_c[1] - 30))
			blit(msg2, 8, P.screen_c)
			flip()
			any_key()
			self.exp.quit()

		# Parse block strings for current session
		blocks = session_structure[self.exp.session_number - 1]
		P.blocks_per_experiment = len(blocks)
		for block in blocks:
			resp, fb = self.parse_exp_condition(block)
			self.exp.block_factors.append({'response_type': resp, 'feedback_type': fb})

		# Generate trials and import figure set specified earlier
		self.exp.trial_factory.generate()
		self.import_figure_set()

		# If session number > 1, log runtime info for session in runtime_info table
		if 'session_info' in self.db.table_schemas.keys() and self.exp.session_number > 1:
			runtime_info = EntryTemplate('session_info')
			for col, value in runtime_info_init().items():
				if col == 'session_number':
					value = self.exp.session_number
				runtime_info.log(col, value)
			self.db.insert(runtime_info)

		# delete previous trials for this session if any exist (essentially assume a do-over)
		self.db.query(self.queries["delete_anon"], q_vars=[P.p_id, self.exp.session_number])
		self.db.update('participants', {'initialized': 1})
		self.log_session_init()


	def log_session_init(self):

		header = {
			"session_structure": self.exp.session_structure,
			"figure_set": self.exp.figure_set_name,
			"practice_session": self.exp.show_practice_display,
		}
		self.exp.log("*************** HEADER START ***************\n")
		for k in header:
			self.exp.log("{0}: {1}\n".format(k, header[k]))
		self.exp.log("**************** HEADER END ****************\n")


	def restore_session(self, user_data):

		# Reload participant data from database into experiment variables
		P.participant_id = user_data[0]
		P.random_seed = user_data[1] # NOTE: is this actually wanted?
		self.exp.session_structure = user_data[2]
		self.exp.session_count = user_data[3]
		self.exp.session_number = user_data[4]
		self.exp.figure_set_name = user_data[5]
		self.exp.handedness = user_data[6]
		self.exp.created = user_data[7]

		self.exp.session_number += 1  # check if last session incomplete and prompt if so?
		P.session_number = self.exp.session_number
		if P.use_log_file:
			log_path = os.path.join(P.local_dir, "logs", "P{0}_log_f.txt".format(self.user_id))
			self.exp.log_f = open(log_path, "w+")

		return True


	def import_figure_set(self):

		if not self.exp.figure_set_name or self.exp.figure_set_name == NA:
			return

		if not self.exp.figure_set_name in self.exp.figure_sets:
			e_msg = "No figure set named '{0}' is registered.".format(self.exp.figure_set_name)
			raise ValueError(e_msg)
		# get sting values of figure file names (minus suffix)
		figure_set = list(self.exp.figure_sets[self.exp.figure_set_name].figures)

		# ensure all figures are pre-loaded, even if not on the default figure list
		for f in figure_set:
			if f[0] not in P.figures and f[0] != "random":
				f_path = os.path.join(P.resources_dir, "figures", f[0])
				if os.path.exists(f_path + ".zip"):
					# Re-generate saved figure from .zip
					self.exp.test_figures[f[0]] = TraceLabFigure(f_path)
				else:
					fill()
					e_msg = (
						"The figure '{0}' listed in the figure set '{1}' wasn't found.\n"
						"Please check that the file is named correctly and try again. "
						"TraceLab will now exit.".format(f[0], self.exp.figure_set_name)
					)
					blit(message(e_msg, blit_txt=False), 5, P.screen_c)
					flip()
					any_key()
					self.exp.quit()
			self.exp.figure_set.append(f)

		# load original ivars file into a named object
		sys.path.append(P.ind_vars_file_path)
		if os.path.exists(P.ind_vars_file_local_path) and not P.dm_ignore_local_overrides:
			for k, v in load_source("*", P.ind_vars_file_local_path).__dict__.items():
				if isinstance(v, IndependentVariableSet):
					new_exp_factors = v
		else:
			for k, v in load_source("*", P.ind_vars_file_path).__dict__.items():
				if isinstance(v, IndependentVariableSet):
					new_exp_factors = v
		new_exp_factors.delete('figure_name')
		new_exp_factors.add_variable('figure_name', str, self.exp.figure_set)

		self.exp.trial_factory.generate(new_exp_factors)


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

		if "X" in feedback:
			fb = "False"
		elif "V" in feedback and "R" in feedback:
			fb = FB_ALL
		elif "R" in feedback:
			fb = FB_RES
		elif "V" in feedback:
			fb = FB_DRAW

		return [resp, fb]


	@property
	def user_id(self):
		return self.__user_id__

	@user_id.setter
	def user_id(self, uid):
		self.__user_id__ = uid
