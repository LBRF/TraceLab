__author__ = 'jono'

"""
NOTE: this entire document only exists because experiment.previous.py was getting too cluttered and I decided to
relocate all session-init logic to a separate class to tidy things up. previous versions of the experiment
all included these methods as part of the experiment class
"""


from os.path import join, exists
import sys
from imp import load_source

from klibs.KLConstants import QUERY_UPD, NA
from klibs import P
from klibs.KLNamedObject import NamedInventory
from klibs.KLCommunication import query, message
from klibs.KLCommunication import user_queries as uq
from klibs.KLGraphics import blit, flip, fill
from klibs.KLUserInterface import any_key
from klibs.KLIndependentVariable import IndependentVariableSet
from klibs.KLEnvironment import EnvAgent
from TraceLabFigure import TraceLabFigure
from FigureSet import FigureSet


PHYS = "physical"
MOTR = "motor"
CTRL = "control"
FB_DRAW = "drawing_feedback"
FB_RES = "results_feedback"
FB_ALL = "all_feedback"
SESSION_FIG = "figure_capture"
SESSION_TRN = "training"
SESSION_TST = "testing"

class TraceLabSession(EnvAgent):
	
	queries = {
	"user_data": "SELECT `id`,`random_seed`,`exp_condition`,`feedback_type`, `session_count`, `sessions_completed`, `figure_set`, `handedness`,`created` FROM `participants` WHERE `user_id` = ?",
	"get_user_id": "SELECT `user_id` FROM `participants` WHERE `id` = ?",
	"session_update": "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?",
	"assign_figure_set": "UPDATE `participants` SET `figure_set` = ?  WHERE `id` = ?",
	"set_initialized": "UPDATE `participants` set `initialized` = 1 WHERE `id` = ?",
	"delete_anon": "DELETE FROM `trials` WHERE `participant_id` = ? AND `session_num` = ?",
	"delete_incomplete": "DELETE FROM `participants` WHERE `initialized` = 0",
	"exp_condition": "UPDATE `participants` SET `exp_condition` = ?, `session_count` = ?, `feedback_type` = ? WHERE `id` = ?",
	"session_data": "SELECT `exp_condition`,`feedback_type`, `session_count`, `sessions_completed`, `figure_set` FROM `participants` WHERE `id` = ?"
	}

	error_strings = {
		"invalid_format": "Experimental condition identifiers must be separated by hyphens, and contain three components:\
						  \nExperimental condition, feedback condition, and the number of sessions.\nPlease try again",
		"invalid_condition": "The experimental condition must commence with any of 'PP', 'MI' or 'CC'.\nPlease try again.",
		"invalid_feedback": "The feedback value was invalid.\nIt must contain any combination of 'V', 'R' or 'X' and be\
		 between one and two characters long.\nPlease try again.",
		"invalid_session_count": "Number of sessions must be a valid integer greater than 0.\nPlease try again."
	}

	user_id = None

	def __init__(self):
		self.__user_id__ = None
		self.__import_figure_sets__()
		if P.development_mode:
			self.init_session(False)
		else:
			self.user_id = query(uq.experimental[1])
			if self.user_id is None:
				self.__generate_user_id__()
			self.init_session()

	def __import_figure_sets__(self):
		# load original complete set of FigureSets for use
		fig_sets_f = join(P.config_dir, "figure_sets.py")
		fig_sets_local_f = join(P.local_dir, "figure_sets.py")
		try:
			sys.path.append(fig_sets_local_f)
			for k, v in load_source("*", fig_sets_local_f).__dict__.iteritems():
				if isinstance(v, FigureSet):
					self.exp.figure_sets[v.name] = v
			if P.dm_ignore_local_overrides:
				raise RuntimeError("ignoring local files")
		except (IOError, RuntimeError):
			sys.path.append(fig_sets_f)
			for k, v in load_source("*", fig_sets_f).__dict__.iteritems():
				if isinstance(v, FigureSet):
					self.exp.figure_sets[v.name] = v

	def __generate_user_id__(self):
		from klibs.KLCommunication import collect_demographics
		# delete all incomplete attempts to create a user to free up username space; no associated records to remove
		self.db.query(self.queries["delete_incomplete"])
		collect_demographics(P.development_mode)
		self.user_id = self.db.query(self.queries["get_user_id"], q_vars=[P.p_id])[0][0]
		self.parse_exp_condition(query(uq.experimental[2]))
		if query(uq.experimental[3]) == "y":
			self.exp.figure_key = query(uq.experimental[4])
			self.db.query(self.queries["assign_figure_set"], QUERY_UPD, q_vars=[self.exp.figure_key, P.p_id])

	def init_session(self):
		# from klibs.KLCommunication import user_queries as uq

			# self.exp.session_number = 1
		try:
			user_data = self.db.query(self.queries['user_data'], q_vars=[self.user_id])[0]
			self.restore_session(user_data)
		except KeyError as e:
			if query(uq.experimental[0]) == "y":
				self.user_id = query(uq.experimental[1])
				if self.user_id is None:
					self.__generate_user_id__()
				return self.init_session()
			else:
				message("Thanks for participating!", "default", P.screen_c, 5, blit_txt=True, fill_screen=True, flip_screen=True)
				any_key()
				self.quit()

		self.import_figure_set()

		# P.user_data = user_data  # used in experiment.py for creating file na,es
		# delete previous trials for this session if any exist (essentially assume a do-over)
		if P.capture_figures_mode:
			self.exp.training_session = True
			self.exp.session_type = SESSION_FIG
		else:
			self.db.query(self.queries["delete_anon"], q_vars=[P.p_id, self.exp.session_number])
			self.exp.training_session = self.exp.session_number not in (1, 5)
			self.exp.session_type = SESSION_TRN if self.exp.training_session else SESSION_TST
		self.db.query(self.queries["set_initialized"], QUERY_UPD, q_vars=[P.p_id])
		# P.demographics_collected = True
		P.practice_session = self.exp.session_number == 1 or (self.exp.session_number == self.exp.session_count and self.exp.exp_condition != PHYS)
		self.log_session_init()

	def log_session_init(self):
		header = {"exp_condition": self.exp.exp_condition,
				  "feedback": self.exp.feedback_type,
				  "figure_set": self.exp.figure_key,
				  "practice_session": self.exp.practice_session,
		}
		self.exp.log("*************** HEADER START****************\n")
		if P.use_log_file:
			for k in header:
				self.exp.log("{0}: {1}\n".format(k, header[k]))
		self.exp.log("*************** HEADER END *****************\n")

	def restore_session(self, user_data):
		# `id`,`random_seed`,`exp_condition`,`session_count`,`feedback_type`,`sessions_completed`,`figure_set`
		P.participant_id, P.random_seed, self.exp.exp_condition, self.exp.feedback_type, self.exp.session_count, self.exp.session_number, self.exp.figure_set_name, self.exp.handedness, self.exp.created = user_data
		self.exp.session_number += 1
		self.exp.log_f = open(join(P.local_dir, "logs", "P{0}_log_f.txt".format(P.participant_id)), "w+")
		print "Practice Conditions: {0}, {1}".format(self.exp.session_number == 1, (self.exp.exp_condition != PHYS and self.exp.session_number == self.exp.session_count))
		if self.exp.session_number == 1 or (self.exp.exp_condition != PHYS and self.exp.session_number == self.exp.session_count):
			self.exp.practice_session = True

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
				f_path = join(P.resources_dir, "figures", f[0])
				self.exp.test_figures[f[0]] = TraceLabFigure(f_path)
			self.exp.figure_set.append(f)

		# load original ivars file into a named object
		sys.path.append(P.ind_vars_file_path)
		if exists(P.ind_vars_file_local_path) and not P.dm_ignore_local_overrides:
			for k, v in load_source("*", P.ind_vars_file_local_path).__dict__.iteritems():
				if isinstance(v, IndependentVariableSet):
					new_exp_factors = v
		else:
			for k, v in load_source("*", P.ind_vars_file_path).__dict__.iteritems():
				if isinstance(v, IndependentVariableSet):
					new_exp_factors = v
		new_exp_factors.delete('figure_name')
		new_exp_factors.add_variable('figure_name', str, self.exp.figure_set)

		self.exp.trial_factory.generate(new_exp_factors)
		self.exp.blocks = self.exp.trial_factory.export_trials()

	def parse_exp_condition(self, condition_str):
		# from klibs.KLCommunication import user_queries as uq
		error_args = {"style":"error",
					  "location":P.screen_c,
					  "registration":5,
					  "blit_txt":True,
					  "flip_screen":True,
					  "clear_screen":True,
					  "wrap_width":200}
		try:
			exp_cond, feedback, sessions = condition_str.split("-")
		except ValueError:
			message(self.error_strings["invalid_format"], **error_args)
			any_key()
			return self.parse_exp_condition(query(uq.experimental[2]))
		if exp_cond not in ["PP", "MI", "CC"]:
			message(self.error_strings["invalid_condition"], **error_args)
			any_key()
			return self.parse_exp_condition(query(uq.experimental[2]))
		feedback = list(feedback)
		for i in feedback:
			if i not in ["V", "R", "X"] or len(feedback) > 2:
				message(self.error_strings["invalid_feedback"], **error_args)
				any_key()
				return self.parse_exp_condition(query(uq.experimental[2]))
		if int(sessions) < 1:
			message(self.error_strings["invalid_session_count"], **error_args)
			any_key()
			return self.parse_exp_condition(query(uq.experimental[2]))


		# first parse the experimental condition
		if exp_cond == "PP":
			self.exp.exp_condition = PHYS
		elif exp_cond == "MI":
			self.exp.exp_condition = MOTR
		elif exp_cond == "CC":
			self.exp.exp_condition = CTRL
		else:
			e_msg = "{0} is not a valid experimental condition identifier.".format(exp_cond)
			raise ValueError(e_msg)
		# then parse the feedback type, if any
		if all(["V" in feedback, "R" in feedback]):
			self.exp.feedback_type = FB_ALL
		elif "R" in feedback:
			self.exp.feedback_type = FB_RES
		elif "V" in feedback:
			self.exp.feedback_type = FB_DRAW
		elif "X" in feedback:
			pass
		else:
			e_msg = "{0} is not a valid feedback state.".format("".join(feedback))
			raise ValueError(e_msg)

		try:
			self.exp.session_count = int(sessions)
		except ValueError:
			e_msg = "Session count requires an integer."
			raise ValueError(e_msg)
		q_vars = [self.exp.exp_condition, self.exp.session_count, self.exp.feedback_type, P.participant_id]
		self.db.query(self.queries["exp_condition"], QUERY_UPD, q_vars=q_vars)

		if self.exp.session_number == 1 or (self.exp.exp_condition in [MOTR, CTRL] and self.exp.session_number == self.exp.session_count):
			self.exp.practice_session = True

	@property
	def user_id(self):
		return self.__user_id__

	@user_id.setter
	def user_id(self, uid):
		self.__user_id__ = uid