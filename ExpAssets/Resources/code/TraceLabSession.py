__author__ = 'jono'

"""
NOTE: this entire document only exists because experiment.previous.py was getting too cluttered and I decided to
relocate all session-init logic to a separate class to tidy things up. previous versions of the experiment
all included these methods as part of the experiment class
"""


from os.path import join, exists
from os import makedirs
from shutil import rmtree
import sys
from imp import load_source

from klibs.KLConstants import QUERY_UPD, NA
from klibs import P
from klibs.KLUtilities import now
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
MOTR = "imagery"
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
	"user_row": "SELECT `user_id`,`random_seed`,`exp_condition`,`feedback_type`, `session_count`, `sessions_completed`, `figure_set`, `handedness`,`created` FROM `participants` WHERE `id` = ?",
	"get_user_id": "SELECT `user_id` FROM `participants` WHERE `id` = ?",
	"session_update": "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?",
	"assign_figure_set": "UPDATE `participants` SET `figure_set` = ?  WHERE `id` = ?",
	"set_initialized": "UPDATE `participants` set `initialized` = 1 WHERE `id` = ?",
	"delete_anon": "DELETE FROM `trials` WHERE `participant_id` = ? AND `session_num` = ?",
	"delete_incomplete_user": "DELETE FROM `participants` WHERE `id` = ?",
	"delete_incomplete_user_sessions": "DELETE FROM `sessions` WHERE `participant_id` = ?",
	"delete_incomplete_user_trials": "DELETE FROM `trials` WHERE `participant_id` = ?",
	"find_incomplete": "SELECT `id`, `user_id`, `created` FROM `participants` WHERE `initialized` = 0",
	"exp_condition": "UPDATE `participants` SET `exp_condition` = ?, `session_count` = ?, `feedback_type` = ? WHERE `id` = ?",
	"session_data": "SELECT `exp_condition`,`feedback_type`, `session_count`, `sessions_completed`, `figure_set` FROM `participants` WHERE `id` = ?",
	"completed_sessions": "SELECT * FROM `sessions` WHERE `participant_id` = ?",
	"completed_trials": "SELECT * FROM `trials` WHERE `participant_id` = ?"
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
		incomplete_participants = self.db.query(self.queries["find_incomplete"])
		if len(incomplete_participants):
			if query(uq.experimental[7]) == "p":
				self.__purge_incomplete__(incomplete_participants)
			else:
				self.__report_incomplete__(incomplete_participants)
		if P.development_mode:
			# Write data to subfolder when in development mode to avoid cluttering
			# data directory with non-participant data
			devmode_data_dir = join(P.data_dir, "devmode")
			if not exists(devmode_data_dir):
				makedirs(devmode_data_dir)
			P.data_dir = devmode_data_dir
		else:
			self.user_id = query(uq.experimental[1])
		if self.user_id is None:
			self.__generate_user_id__()
		self.init_session()

	def __report_incomplete__(self, participant_ids):
		log = open(join(P.local_dir, "uninitialized_users_{0}".format(now(True))), "w+")
		header = ["user_id","random_seed","exp_condition","feedback_type", "session_count", "sessions_completed", "figure_set", "handedness","created", "session_rows", "trial_rows"]
		log.write("\t".join(header))
		for p in participant_ids:
			log.write("\n")
			p_data = self.db.query(self.queries['user_row'], q_vars=[p[0]])[0]
			p_data.append(len(self.db.query(self.queries['completed_sessions'], q_vars=[p[0]])))
			p_data.append(len(self.db.query(self.queries['completed_trials'], q_vars=[p[0]])))
			log.write("\t".join([str(i) for i in p_data]))
		log.close()
		self.exp.quit()

	def __purge_incomplete__(self, participant_ids):
		for p in participant_ids:
			self.db.query(self.queries["delete_incomplete_user"], q_vars=[p[0]])
			self.db.query(self.queries["delete_incomplete_user_sessions"], q_vars=[p[0]])
			self.db.query(self.queries["delete_incomplete_user_trials"], q_vars=[p[0]])

			try:
				rmtree(join(P.data_dir, "{0}_{1}".format(*p[1:])))
			except OSError:
				pass
		try:
			self.db.commit()
		except: # if old klibs, use old db accessing convention
			self.db.db.commit()

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
		collect_demographics(P.development_mode)
		self.user_id = self.db.query(self.queries["get_user_id"], q_vars=[P.p_id])[0][0]
		self.parse_exp_condition(query(uq.experimental[2]))
		if query(uq.experimental[3]) == "y":
			self.__get_figure_set_name__()

	def __get_figure_set_name__(self):
		name = query(uq.experimental[4])
		if not name in self.exp.figure_sets:
			if query(uq.experimental[0]) == "y":
				return self.__get_figure_set_name__()
			else:
				name = None
		self.exp.figure_key = name
		self.db.query(self.queries["assign_figure_set"], QUERY_UPD, q_vars=[self.exp.figure_key, P.p_id])

	def init_session(self):

		try:
			user_data = self.db.query(self.queries['user_data'], q_vars=[self.user_id])[0]
			self.restore_session(user_data)
		except IndexError as e:
			if query(uq.experimental[0]) == "y":
				self.user_id = query(uq.experimental[1])
				if self.user_id is None:
					self.__generate_user_id__()
				return self.init_session()
			else:
				message("Thanks for participating!", "default", P.screen_c, 5, blit_txt=True, clear_screen=True, flip_screen=True)
				any_key()
				self.exp.quit()

		self.import_figure_set()

		# delete previous trials for this session if any exist (essentially assume a do-over)
		if P.capture_figures_mode:
			self.exp.training_session = True
			self.exp.session_type = SESSION_FIG
		else:
			self.db.query(self.queries["delete_anon"], q_vars=[P.p_id, self.exp.session_number])
			self.exp.training_session = self.exp.session_number not in (1, 5)
			self.exp.session_type = SESSION_TRN if self.exp.training_session else SESSION_TST
		self.db.query(self.queries["set_initialized"], QUERY_UPD, q_vars=[P.p_id])
		self.log_session_init()

	def log_session_init(self):
		header = {"exp_condition": self.exp.exp_condition,
				  "feedback": self.exp.feedback_type,
				  "figure_set": self.exp.figure_key,
				  "practice_session": self.exp.show_practice_display,
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
		self.exp.log_f = open(join(P.local_dir, "logs", "P{0}_log_f.txt".format(self.user_id)), "w+")
		if self.exp.session_number == 1:
			self.exp.show_practice_display = True
		elif self.exp.session_count > 1 and self.exp.session_number == self.exp.session_count:
			# if multi-session and on final session, and participant condition is imagery/control,
			# set session condition to physical and show physical practice animation.
			if self.exp.exp_condition != PHYS:
				self.exp.exp_condition = PHYS
				self.exp.show_practice_display = True

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
				pickle_file = f_path + "_{0}x{1}.pickle".format(P.screen_x, P.screen_y)
				# Try to load pickled figure if it exists (much faster)
				if os.path.exists(pickle_file):
					with open(pickle_file, 'rb') as p:
						self.exp.test_figures[f[0]] = pickle.load(p)
				else:
					# If no picked figure, generate figure from .zip and pickle
					# for future runs.
					self.exp.test_figures[f[0]] = TraceLabFigure(f_path)
					with open(pickle_file, 'wb') as p:
						pickle.dump(self.exp.test_figures[f[0]], p, -1)
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
					  "align": "center"}
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


	@property
	def user_id(self):
		return self.__user_id__

	@user_id.setter
	def user_id(self, uid):
		self.__user_id__ = uid