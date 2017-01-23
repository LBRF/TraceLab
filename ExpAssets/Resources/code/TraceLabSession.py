__author__ = 'jono'

"""
NOTE: this entire document only exists because experiment.py was getting too cluttered and I decided to
relocate all session-init logic to a separate class to tidy things up. previous versions of the experiment
all included these methods as part of the experiment class
"""


from os.path import join, exists
import sys
from imp import load_source

from klibs.KLConstants import QUERY_UPD
from klibs import P
from klibs.KLNamedObject import NamedInventory
from klibs.KLCommunication import query, message
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
	"user_data_new": "SELECT * FROM `participants` WHERE `id` = ?",
	"user_data_prev": "SELECT * FROM `participants` WHERE `local_id` = ?",
	"session_update": "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?",
	"assign_figure_set": "UPDATE `participants` SET `figure_set` = ? WHERE `id` = ?",
	"set_initialized": "UPDATE `participants` set `initialized` = 1 WHERE `id` = ?",
	"delete_anon": "DELETE FROM `trials` WHERE `participant_id` = ? AND `session_num` = ?",
	"delete_incomplete": "DELETE FROM `participants` WHERE `initialized` = 0"
	}

	def __init__(self):
		from klibs.KLCommunication import user_queries
		self.__import_figure_sets__()
		self.init_session(query(user_queries.experimental[1]) if not P.development_mode else False)

	def __import_figure_sets__(self):
		# load original complete set of FigureSets for use
		for k, v in load_source("*", join(P.resources_dir, "figure_sets.py")).__dict__.iteritems():
			if isinstance(v, FigureSet):
				self.exp.figure_sets[v.name] = v

	def init_session(self, local_id=None):
		from klibs.KLCommunication import user_queries

		# delete all incomplete attempts to create a user to free up username space; no associated records to remove
		self.db.query(self.queries["delete_incomplete"])

		# if an id is provided, continue from a previous or incomplete session
		if local_id:
			try:
				user_data = self.db.query(self.queries['user_data_prev'], q_vars=[local_id]).fetchall()[0]
				P.p_id = user_data[0]
				P.random_seed = str(user_data[2])
				if not self.restore_session():
					P.session_number = 1
			except IndexError:
				retry = query(user_queries.experimental[0])
				if retry == 'y':
					return self.init_session(query(user_queries.experimental[1]))
				else:
					fill()
					message("Thanks for participating!", location=P.screen_c, flip_x=P.flip_x)
					flip()
					any_key()
					self.quit()
		else:
			P.session_number = 1
			try:
				user_data = self.db.query(self.queries['user_data_new'], q_vars=[P.p_id]).fetchall()[0]
			except IndexError:
				# new user, get demographics
				from klibs.KLCommunication import collect_demographics
				collect_demographics(P.development_mode)

				# set the number of sessions completed to 0
				self.db.query(self.queries['session_update'], QUERY_UPD, q_vars=[0, P.p_id])
				# now set updated user data in the experiment context
				user_data = self.db.query(self.queries['user_data_new'], q_vars=[P.p_id]).fetchall()[0]

				# manage figure sets, if in use for this participant
				if query(user_queries.experimental[3]) == "y":
					self.exp.figure_set_name = query(user_queries.experimental[4])
					self.db.query(self.queries["assign_figure_set"], QUERY_UPD, q_vars=[self.exp.figure_set_name, P.p_id])

		self.import_figure_set()

		P.user_data = user_data

		# delete previous trials for this session if any exist (essentially assume a do-over)
		if not P.capture_figures_mode:
			self.db.query(self.queries["delete_anon"], q_vars=[P.p_id, P.session_number])

			if P.session_number == 1:
				if not self.restore_session():
					self.parse_exp_condition(query(user_queries.experimental[2]))
			self.exp.training_session = P.session_number not in (1, 5)
			self.exp.session_type = SESSION_TRN if self.exp.training_session else SESSION_TST
		else:
			self.exp.training_session = True
			self.exp.session_type = SESSION_FIG
		self.db.query(self.queries["set_initialized"], QUERY_UPD, q_vars=[P.p_id])
		P.demographics_collected = True

	def import_figure_set(self):
		if not self.exp.figure_set_name:
			return

		if not self.exp.figure_set_name in self.exp.figure_sets:
			e_msg = "No figure set named '{0}' is registered.".format(self.exp.figure_set_name)
			raise ValueError(e_msg)
		# get sting values of figure file names (minus suffix)
		figure_set = list(self.exp.figure_sets[self.exp.figure_set_name].figures)

		# ensure all figures are pre-loaded, even if not on the default figure list
		for f in figure_set:
			if f[0] not in P.figures:
				f_path = join(P.resources_dir, "figures", f[0])
				self.exp.test_figures[f] = TraceLabFigure(f_path)
			self.exp.figure_set.append(f)

		# load original ivars file into a named object
		sys.path.append(P.ind_vars_file_path)
		for k, v in load_source("*", P.ind_vars_file_path).__dict__.iteritems():
			if isinstance(v, IndependentVariableSet):
				new_exp_factors = v
		new_exp_factors.delete('figure_name')
		new_exp_factors.add_variable('figure_name', str, self.exp.figure_set)

		self.exp.trial_factory.generate(new_exp_factors)

	def restore_session(self):
		import unicodedata
		session_data_str = "SELECT `exp_condition`,`feedback_type`, `session_count`, `sessions_completed`, `figure_set` FROM `participants` WHERE `id` = ?"
		try:
			session_data = list(self.db.query(session_data_str, q_vars=[P.p_id]).fetchall()[0])
			session_data[0] = unicodedata.normalize('NFKD', session_data[0]).encode('ascii', 'ignore')
			session_data[1] = unicodedata.normalize('NFKD', session_data[1]).encode('ascii', 'ignore')
			self.exp.exp_condition, self.exp.feedback_type, self.exp.session_count, P.session_number, self.exp.figure_set_name = session_data
			P.session_number += 1

			if P.session_number == 1 or (self.exp.exp_condition in [MOTR, CTRL] and P.session_number == P.session_count):
				self.exp.practice_session = True

		except (IndexError, TypeError):
			return False
		return True

	def parse_exp_condition(self, condition_str):
		try:
			exp_cond, feedback, sessions = condition_str.split("-")
		except ValueError:
			from klibs.KLCommunication import user_queries
			message(
				"Experimental condition identifiers must be separated by hyphens, and hyphens only. Please try again")
			any_key()
			return self.parse_exp_condition(query(user_queries.experimental[2]))
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
		if feedback == "VV":
			self.exp.feedback_type = FB_DRAW
		elif feedback == "RR":
			self.exp.feedback_type = FB_RES
		elif feedback == "VR":
			self.exp.feedback_type = FB_ALL
		elif feedback == "XX":
			pass
		else:
			e_msg = "{0} is not a valid feedback state.".format(exp_cond)
			raise ValueError(e_msg)

		try:
			self.exp.session_count = int(sessions)
		except ValueError:
			e_msg = "Session count requires an integer."
			raise ValueError(e_msg)

		q_str = "UPDATE `participants` SET `exp_condition` = ?, `session_count` = ?, `feedback_type` = ? WHERE `id` = ?"
		self.db.query(q_str, QUERY_UPD, q_vars=[self.exp.exp_condition, self.exp.session_count, self.exp.feedback_type, P.p_id])

		if P.session_number == 1 or (self.exp.exp_condition in [MOTR, CTRL] and P.session_number == P.session_count):
			self.exp.practice_session = True