# "fixate" at draw start; show image (maintain "fixation"; draw after SOA
__author__ = "Jonathan Mulle"
import shutil, sys
sys.path.append("ExpAssets/Resources/code/")
from sdl2 import SDL_MOUSEBUTTONDOWN
from random import choice
from copy import copy

from klibs.KLExceptions import TrialException
from klibs import P
from klibs.KLConstants import NA, RC_DRAW, RECT_BOUNDARY, CIRCLE_BOUNDARY, STROKE_OUTER, QUERY_UPD
from klibs.KLUtilities import *
from klibs.KLGraphics import blit, fill, flip, clear
from klibs.KLGraphics.KLDraw import Ellipse, Rectangle
from klibs.KLCommunication import message, query, collect_demographics
from klibs.KLUserInterface import any_key, ui_request
from klibs.KLExperiment import Experiment
from TraceLabFigure import TraceLabFigure
from ButtonBar import Button, ButtonBar
from KeyFrames import KeyFrame, FrameSet
from klibs.KLBoundary import BoundaryInspector
from hashlib import sha1
try:
	import u3
except ImportError:
	pass

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255,0,0,255)
GREEN = (0,255,0,255)
BOT_L = 0
TOP_L = 1
TOP_R = 2

# condition codes; jon hates retyping strings
PHYS = "physical"
MOTR = "motor"
CTRL = "control"
FB_DRAW = "drawing_feedback"
FB_RES = "results_feedback"
FB_ALL = "all_feedback"
SESSION_FIG =  "figure_capture"
SESSION_TRN = "training"
SESSION_TST = "testing"

"""
Notes:

1) Currently ALL exp conditions still run the physical practice on the LAST session
2) To include random figures in the figure set, add a "random" line
3) if no figure set is provided, the figures listed in TraceLab_independent_variables.py are used
4) set names can't contain underscores for stupid reasons
"""


class TraceLab(Experiment, BoundaryInspector):

	# session vars
	p_dir = None
	fig_dir = None
	training_session = None
	session_type = None
	exp_condition = None
	session_count = None
	feedback_type = False
	practice_session = False   # ie. this session should include the practice display
	lj_codes = None
	lj_spike_interval = 0.01
	lj = None
	auto_generate_count = None

	# graphical elements
	imgs = {}

	# value_slider = None
	origin_proto = None
	origin_active = None
	origin_inactive = None
	origin_active_color = GREEN
	origin_inactive_color = RED
	origin_size = None
	origin_pos = None
	origin_boundary = None
	tracker_dot_proto = None
	tracker_dot = None
	button_bar = None

	instructions = None
	loading_msg = None
	control_fail_msg = None
	next_trial_msg = None
	next_trial_box = None
	next_trial_button_loc = None
	next_trial_button_bounds = None
	response_window_extension = 1 # second
	response_window = None  # animate_time + constant

	# debug & configuration
	sample_exposure_time = 4500

	# dynamic trial vars
	animate_finish = None
	boundaries = {}
	use_random_figures = False
	drawing = []
	drawing_name = None
	rt = None  # time to initiate responding post-stimulus
	mt = None  # time to start and complete response
	it = None  # time between arriving at response origin and intiating response (ie. between RT and MT)
	mode = None
	control_response = None
	test_figures = {}
	figure = None
	figure_dots = None
	figure_segments = None
	control_question = None  # ie. which question the control will be asked to report an answer for

	# configured trial factors (dynamically loaded per-trial
	animate_time = None
	figure_name = None
	figure_set = None
	figure_set_name = None

	# practice stuff
	narration = None
	__practicing__ = False
	practice_buttons = None
	practice_instructions = None
	practice_button_bar = None
	practice_kf = None

	def __init__(self, *args, **kwargs):
		super(TraceLab, self).__init__(*args, **kwargs)
		P.flip_x = P.mirror_mode

	def __practice__(self):
		self.figure_name = P.practice_figure
		self.animate_time = P.practice_animation_time
		self.setup_response_collector()
		self.trial_prep()
		P.clock.start()
		self.trial()
		P.clock.stop()
		self.trial_clean_up()

	def __review_figure__(self):
		fill()
		if P.auto_generate:
			msg = "Generating figure {0} of {1}".format((P.auto_generate_count + 1) - self.auto_generate_count, P.auto_generate_count)
			message(msg, "default", registration=5, location=P.screen_c, flip=True)

		while not self.figure:
			ui_request()
			try:
				self.figure = TraceLabFigure(self)
			except RuntimeError:
				pass
		self.animate_time = 5000.0
		self.figure.render()
		self.figure.prepare_animation()
		if not P.auto_generate:
			self.figure.animate()
			flip()
			any_key()
			resp = self.query("(s)ave, (d)iscard, (r)eplay or (q)uit?", accepted=['s', 'd', 'r', 'q'])
			if resp == "q":
				return True
			if resp == "r":
				return False
			if resp == "d":
				self.figure = None
				return False
			if resp == "s":
				f_name = self.query("Enter a filename for this figure (omitting suffixes):") + ".tlf"
				fill()
				message("Saving... ", flip=True)
				self.figure.write_out(f_name)

		if P.auto_generate:
			self.auto_generate_count -= 1
			self.figure.write_out("template_{0}.tlf".format(time.time()))
			if self.auto_generate_count == 0:
				return True

		# reset stuff before the experiment proper begins

	def setup(self):
		from klibs.KLCommunication import user_queries

		self.init_session(query(user_queries.experimental[1]) if not P.development_mode else False)

		if P.labjacking:
			self.lj = u3.U3()
			self.getCalibrationData()
			self.lj_codes = {
			"baseline": u3.DAC0_8(self.lj.voltageToDACBits(0.0, dacNumber=0, is16Bits=False)),
			"origin_red_on_code": u3.DAC0_8(self.lj.voltageToDACBits(1.0, dacNumber=0, is16Bits=False)),
			"origin_green_on_code": u3.DAC0_8(self.lj.voltageToDACBits(2.0, dacNumber=0, is16Bits=False)),
			"origin_off_code": u3.DAC0_8(self.lj.voltageToDACBits(3.0, dacNumber=0, is16Bits=False))}
			# self.configU3(FIOAnalog=1)
			self.getFeedback(P.eeg_codes['baseline'])

		self.loading_msg = message("Loading...", "default", blit_txt=False)
		fill()
		blit(self.loading_msg, 5, P.screen_c)
		flip()
		self.origin_size = P.origin_size
		if P.capture_figures_mode:
			self.fig_dir = os.path.join(P.resources_dir, "figures")
		else:
			self.p_dir = os.path.join(P.data_dir, "p{0}_{1}".format(P.user_data[0], P.user_data[-2]))
			self.fig_dir = os.path.join(self.p_dir, self.session_type, "session_" + str(P.session_number))
			if os.path.exists(self.fig_dir):
				shutil.rmtree(self.fig_dir)
			os.makedirs(self.fig_dir)

		self.origin_proto = Ellipse(self.origin_size)

		if P.tracker_dot_perimeter > 0:
			tracker_dot_stroke = [P.tracker_dot_perimeter, P.tracker_dot_perimeter_color, STROKE_OUTER]
		else:
			tracker_dot_stroke = None
		self.tracker_dot_proto = Ellipse(P.tracker_dot_size, stroke=tracker_dot_stroke, fill=P.tracker_dot_color)
		self.tracker_dot = self.tracker_dot_proto.render()
		self.txtm.add_style('instructions', 18, [255, 255, 255, 255])
		self.txtm.add_style('error', 18, [255, 0, 0, 255])
		self.txtm.add_style('tiny', 12, [255, 255,255, 255])
		self.txtm.add_style('small', 14, [255, 255,255, 255])

		if P.capture_figures_mode:
			self.capture_figures()

		btn_vars = (self, [(str(i), P.btn_size, None) for i in range(1,6)], P.btn_size, P.btn_s_pad, P.y_pad, P.btn_instrux)
		self.button_bar = ButtonBar(*btn_vars)
		self.use_random_figures = P.session_number not in (1, 5)
		self.origin_proto.fill = self.origin_active_color
		self.origin_active = self.origin_proto.render()
		self.origin_proto.fill = self.origin_inactive_color
		self.origin_inactive = self.origin_proto.render()
		instructions_file = "{0}_group_instructions.txt"
		if self.exp_condition == PHYS:
			instructions_file = instructions_file.format("physical")
		elif self.exp_condition == MOTR:
			instructions_file = instructions_file.format("imagery")
		else:
			instructions_file = instructions_file.format("control")

		instructions_file = os.path.join(P.resources_dir, "Text", instructions_file)
		self.instructions = message(open(instructions_file).read(), "instructions", blit_txt=False)
		self.control_fail_msg = message("Please keep your finger on the start area for the complete duration.", 'error', blit_txt=False )
		self.next_trial_msg = message(P.next_trial_message, 'default', blit_txt=False)
		self.next_trial_box = Rectangle(300, 75, (2, (255,255,255)))
		self.next_trial_button_loc = (P.screen_c[0], P.screen_c[1] - 50)
		xy_1 = (self.next_trial_button_loc[0] - 150, self.next_trial_button_loc[1] - 33)
		xy_2 = (self.next_trial_button_loc[0] + 150, self.next_trial_button_loc[1] + 33)
		self.add_boundary("next trial button", (xy_1, xy_2), RECT_BOUNDARY)

		#####
		# practice session vars & elements
		#####
		if not P.dm_override_practice:
			if (self.exp_condition == PHYS and self.session_number == 1) or P.session_number == self.session_count:
				key_frames_f = "physical_key_frames"
			elif self.exp_condition == MOTR:
				key_frames_f = "imagery_key_frames"
			else:
				key_frames_f = "control_key_frames"

			self.practice_kf = FrameSet(self, key_frames_f, "assets")
			self.practice_instructions = message(P.practice_instructions, "instructions", blit_txt=False)
			practice_buttons = [('Replay', [200,100], self.practice), ('Practice', [200,100], self.__practice__),\
								('Begin', [200,100], any_key)]
			self.practice_button_bar = ButtonBar(self, practice_buttons, [200, 100], P.btn_s_pad, P.y_pad, finish_button=False)

		# import figures for use during testing sessions
		fill()
		blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		flip()
		for f in P.figures:
			ui_request()
			self.test_figures[f] = TraceLabFigure(self, os.path.join(P.resources_dir, "figures", f))

		clear()
		if P.enable_practice and P.practice_session:
			message(P.practice_instructions, "instructions", registration=5, location=P.screen_c, blit_txt=True)
			flip()
			any_key()
			self.practice()

	def block(self):
		fill()
		blit(self.instructions, registration=5, location=P.screen_c, flip_x=P.flip_x)
		flip()
		any_key()

	def setup_response_collector(self):
		self.rc.uses(RC_DRAW)
		self.rc.end_collection_event = 'response_period_end'
		self.rc.draw_listener.start_boundary = 'start'
		self.rc.draw_listener.stop_boundary = 'stop'
		self.rc.draw_listener.show_active_cursor = False
		self.rc.draw_listener.show_inactive_cursor = True
		self.rc.draw_listener.origin = self.origin_pos
		self.rc.draw_listener.interrupts = True
		self.rc.display_callback = self.display_refresh
		self.rc.display_callback_args = [True]
		if P.demo_mode:
			self.rc.draw_listener.render_real_time = True

	def trial_prep(self):
		self.control_question = choice(["LEFT","RIGHT","UP","DOWN"])
		self.rt = 0.0
		self.it = 0.0
		self.animate_time = int(self.animate_time)
		self.drawing = NA
		self.control_response = -1
		fill()
		if self.training_session:
			blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		flip()
		failed_generations = 0
		self.figure = None
		if self.figure_name == "random":
			while not self.figure:
				try:
					self.figure = TraceLabFigure(self)
				except RuntimeError as e:
					failed_generations += 1
					if failed_generations > 10:
						print e.message
						self.quit()
					continue
		else:
			self.figure = self.test_figures[self.figure_name]
			self.figure.animate_target_time = self.animate_time
		self.origin_pos = list(self.figure.frames[0])
		if P.flip_x:
			self.origin_pos[0] = P.screen_x - self.origin_pos[0]
		self.add_boundary("origin", [self.origin_pos, self.origin_size // 2], CIRCLE_BOUNDARY)
		self.origin_boundary = [self.origin_pos, self.origin_size // 2]
		self.rc.draw_listener.add_boundaries([('start', self.origin_boundary, CIRCLE_BOUNDARY),
											  ('stop', self.origin_boundary, CIRCLE_BOUNDARY)])
		if P.demo_mode:
			self.figure.render()
		self.figure.prepare_animation()

		# let participant self-initiate next trial
		fill()
		blit(self.next_trial_box, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		blit(self.next_trial_msg, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		flip()
		flush()
		next_trial_button_clicked = False
		if P.demo_mode:
			show_mouse_cursor()
		while not next_trial_button_clicked:
			event_queue = pump(True)
			for e in event_queue:
				if e.type == SDL_MOUSEBUTTONDOWN:
					next_trial_button_clicked = self.within_boundary("next trial button", [e.button.x, e.button.y])
				ui_request(e)
		if P.demo_mode:
			hide_mouse_cursor()

	def trial(self):
		self.figure.animate()
		self.animate_finish = P.clock.trial_time
		try:
			if self.exp_condition == PHYS:
				self.physical_trial()
			if self.exp_condition == MOTR:
				if P.session_number == 5:
					self.physical_trial()
				else:
					self.imagery_trial()
			if self.exp_condition == CTRL:
				if P.session_number == 5:
					self.physical_trial()
				else:
					self.control_trial()
		except TrialException as e:
			fill()
			message(P.trial_error_msg, "error")
			any_key()
			raise TrialException(e.message)
		fill()
		flip()

		if not P.practicing and P.labjacking:
			self.lj.getFeedback(self.lj_codes['origin_off_code'])
			if self.lj_spike_interval: time.sleep(self.lj_spike_interval)
			self.lj.getFeedback(self.lj_codes['baseline'])

		if self.__practicing__:
			return

		return {
			"block_num": P.block_number,
			"trial_num": P.trial_number,
			"session_num": P.session_number,
			"condition": self.exp_condition,
			"figure_type": self.figure_name,
			"figure_file": self.figure.file_name,
			"stimulus_gt": self.animate_time,
			"stimulus_mt": self.figure.animate_time,
			"avg_velocity": self.figure.avg_velocity,
			"path_length": self.figure.path_length,
			"trace_file": self.tracing_name if self.exp_condition in PHYS else NA,
			"rt": self.rt,
			"it": self.it,
			"control_question": self.control_question if self.exp_condition == CTRL else NA,
			"control_response": self.control_response,
			"mt": self.mt,
		}

	def trial_clean_up(self):
		if not self.__practicing__:
			self.figure.write_out()
			self.figure.write_out(self.tracing_name, self.drawing)
		self.rc.draw_listener.reset()
		self.button_bar.reset()


	def clean_up(self):
		# if the entire experiment is successfully completed, update the sessions_completed column
		q_str = "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?"
		self.db.query(q_str, QUERY_UPD, q_vars = [P.session_number, P.participant_id])

	def display_refresh(self, flip=True):
		fill()
		origin = self.origin_active  if self.rc.draw_listener.active else self.origin_inactive
		blit(origin, 5, self.origin_pos, flip_x=P.flip_x)
		if P.dm_render_progress or self.feedback_type in (FB_ALL, FB_DRAW):
			try:
				drawing = self.rc.draw_listener.render_progress()
				blit(drawing, 5, P.screen_c, flip_x=P.flip_x)
			except TypeError:
				pass
		if flip:
			flip()


	def init_session(self, id_str=None):
		from klibs.KLCommunication import user_queries

		new_participant = id_str is None

		if id_str:
			try:
				userhash = sha1(id_str).hexdigest()
				user_data_str = "SELECT * FROM `participants` WHERE `userhash` = ?"
				user_data = self.db.query(user_data_str, q_vars=[userhash]).fetchall()[0]
				P.participant_id = user_data[0]
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
			user_data_str = "SELECT * FROM `participants` WHERE `id` = ?"
			try:
				user_data = self.db.query(user_data_str, q_vars=[P.participant_id]).fetchall()[0]
			except IndexError:
				# new user, get demographics
				from klibs.KLCommunication import collect_demographics
				collect_demographics(P.development_mode)

				# set the number of sessions completed to 0
				self.db.query("UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?",
							  QUERY_UPD, q_vars=[0, P.participant_id])

				# now set updated user data in the experiment context
				user_data = self.db.query(user_data_str, q_vars=[P.participant_id]).fetchall()[0]

				# manage figure sets, if in use for this participant
				if query(user_queries.experimental[3]) == "y":
					q_str = "UPDATE `participants` SET `figure_set` = ? WHERE `id` = ?"
					self.figure_set_name = query(user_queries.experimental[4])
					self.db.query(q_str, QUERY_UPD, q_vars=[self.figure_set_name, P.participant_id])


		self.import_figure_set()

		P.user_data = user_data

		# delete previous trials for this session if any exist (essentially assume a do-over)
		if not P.capture_figures_mode:
			q_str = "DELETE FROM `trials` WHERE `participant_id` = ? AND `session_num` = ?"
			self.db.query(q_str, q_vars=[P.participant_id, P.session_number])
			if P.session_number == 1:
				if not self.restore_session():
					self.parse_exp_condition(query(user_queries.experimental[2]))
			self.training_session = P.session_number not in (1,5)
			self.session_type = SESSION_TRN if self.training_session else SESSION_TST
		else:
			self.training_session = True
			self.session_type = SESSION_FIG
		P.demographics_collected = True
	
	def import_figure_set(self):
		if not self.figure_set_name:
			return

		from klibs.KLIndependentVariable import IndependentVariableSet
		from imp import load_source

		self.figure_set = []
		for f in open(os.path.join(P.resources_dir, "figure_sets", self.figure_set_name+".txt")).read().split("\n"):
			f_path = os.path.join(P.resources_dir, "figures", f + ".zip")
			if not os.path.exists(f_path):
				fill()
				e_msg = "One or more figures listed in the figure set '{0}' weren't found.\n " \
						"Please check for errors and try again. TraceLab will now exit.".format(self.figure_set_name)
				message(e_msg, location=P.screen_c, registration=5, flip_screen=True)
				any_key()
				self.quit()

		 	# ensure all figures are pre-loaded, even if not on the default figure list
			if f not in P.figures:
				self.test_figures[f] = TraceLabFigure(self, f_path)
			self.figure_set.append(f)

		# load original ivars file into a named object
		sys.path.append(P.ind_vars_file_path)
		for k, v in load_source("*", P.ind_vars_file_path).__dict__.iteritems():
			if isinstance(v, IndependentVariableSet):
				new_exp_factors = v
		new_exp_factors.delete('figure_name')
		new_exp_factors.add_variable('figure_name', str, self.figure_set)

		self.trial_factory.generate(new_exp_factors)


	def restore_session(self):
		session_data_str = "SELECT `exp_condition`,`feedback_type`, `session_count`, `sessions_completed`, `figure_set` FROM `participants` WHERE `id` = ?"
		try:
			session_data = self.db.query(session_data_str, q_vars=[P.participant_id]).fetchall()[0]
			self.exp_condition, self.feedback_type, self.session_count, P.session_number, self.figure_set_name = session_data
			P.session_number += 1

			if P.session_number == 1 or (self.exp_condition in [MOTR, CTRL] and P.session_number == P.session_count):
				self.practice_session = True

		except (IndexError, TypeError):
			return False

	def parse_exp_condition(self, condition_str):
		try:
			exp_cond, feedback, sessions = condition_str.split("-")
		except ValueError:
			from klibs.KLCommunication import user_queries
			message("Experimental condition identifiers must be separated by hyphens, and hyphens only. Please try again")
			any_key()
			return self.parse_exp_condition(query(user_queries.experimental[2]))

		# first parse the experimental condition
		if exp_cond == "PP":
			self.exp_condition = PHYS
		elif exp_cond == "MI":
			self.exp_condition = MOTR
		elif exp_cond == "CC":
			self.exp_condition = CTRL
		else:
			e_msg = "{0} is not a valid experimental condition identifier.".format(exp_cond)
			raise ValueError(e_msg)

		# then parse the feedback type, if any
		if feedback == "VV":
			self.feedback_type = FB_DRAW
		elif feedback == "RR":
			self.feedback_type = FB_RES
		elif feedback == "VR":
			self.feedback_type = FB_ALL
		elif feedback == "XX":
			pass
		else:
			e_msg = "{0} is not a valid feedback state.".format(exp_cond)
			raise ValueError(e_msg)

		try:
			self.session_count = int(sessions)
		except ValueError:
			e_msg = "Session count requires an integer."
			raise ValueError(e_msg)

		q_str = "UPDATE `participants` SET `exp_condition` = ?, `session_count` = ?, `feedback_type` = ? WHERE `id` = ?"
		self.db.query(q_str, QUERY_UPD, q_vars=[self.exp_condition, self.session_count, self.feedback_type, P.participant_id])

		if P.session_number == 1 or (self.exp_condition in [MOTR, CTRL] and P.session_number == P.session_count):
			self.practice_session = True

	def imagery_trial(self):
		fill()
		blit(self.origin_inactive, 5, self.origin_pos, flip_x=P.flip_x)
		flip()
		start = P.clock.trial_time
		if not P.practicing and P.labjacking:
			self.lj.getFeedback(self.lj_codes['origin_red_on_code'])
			if self.lj_spike_interval:
				time.sleep(self.lj_spike_interval)
			self.lj.getFeedback(self.lj_codes['baseline'])
		start = P.clock.trial_time
		if P.demo_mode:
			show_mouse_cursor()
		at_origin = False
		while not at_origin:
			if self.within_boundary('origin', mouse_pos()):
				at_origin = True
				self.rt = P.clock.trial_time - start
			ui_request()

		fill()
		blit(self.origin_active, 5, self.origin_pos, flip_x=P.flip_x)
		flip()
		if not P.practicing and P.labjacking:
			self.lj.getFeedback(self.lj_codes['origin_green_on_code'])
			if self.lj_spike_interval:
				time.sleep(self.lj_spike_interval)
			self.lj.getFeedback(self.lj_codes['baseline'])
		while at_origin:
			if not self.within_boundary('origin', mouse_pos()):
				at_origin = False
		self.mt = P.clock.trial_time - (self.rt + start)
		if P.demo_mode:
			hide_mouse_cursor()

	def physical_trial(self):
		start = P.clock.trial_time
		self.rc.collect()
		self.rt = self.rc.draw_listener.start_time - start
		self.drawing = self.rc.draw_listener.responses[0][0]
		self.it = self.rc.draw_listener.first_sample_time - (self.rt + start)

		self.mt = self.rc.draw_listener.responses[0][1]
		if self.feedback_type in (FB_ALL, FB_RES) and not self.__practicing__:
			flush()
			fill()
			blit(self.figure.render(trace=self.drawing), 5, P.screen_c, flip_x=P.flip_x)
			flip()
			start = time.time()
			while time.time() - start < P.max_feedback_time / 1000.0:
				ui_request()

	def control_trial(self):
		self.button_bar.update_message(P.btn_instrux.format(self.control_question))
		self.button_bar.render()
		self.button_bar.collect_response()
		self.rt = self.button_bar.rt
		self.mt = self.button_bar.mt
		self.control_response = self.button_bar.response

	def capture_figures(self):
		self.animate_time = 5000.0
		self.auto_generate_count = P.auto_generate_count
		if P.auto_generate:
			fill()
			message("Press command+q at any time to exit.\nPress any key to continue.", "default", registration=5, location=P.screen_c, flip=True)
			any_key()
			finished = False
		else:
			fill()
			msg = "Quitting (command+q) may be unresponsive during autogeneration.\n" \
				  "Use the program 'ActivityMonitor' to kill ALL Python processes.\n" \
				  "TraceLab will automatically exit when figure generation is complete.\n \n" \
				  "Press any key to begin generating."
			message(msg, "default", registration=5, location=P.screen_c, flip=True)
			any_key()
			finished = self.auto_generate_count == 0
		io_errors = []
		while not finished:
			try:
				finished = self.__review_figure__()
				self.figure = None
			except IOError:
				io_errors.append((P.auto_generate_count + 1) - self.auto_generate_count)
				if len(io_errors) > 10:
					print "\n".join(io_errors)
					break
		self.quit()

	def practice(self, play_key_frames=True, callback=None):
		self.__practicing__ = True

		if callback == self.__practice__:
			play_key_frames = False
			self.__practice__()
		elif callback == self.practice:
			play_key_frames = True
		elif callback == any_key:
			self.__practicing__ = False
			return any_key()

		if play_key_frames:
			self.practice_kf.play()

		self.practice_button_bar.reset()
		self.practice_button_bar.render()
		P.clock.start()
		cb = self.practice_button_bar.collect_response()
		P.clock.stop()

		self.__practicing__ = False

		return self.practice(callback=cb)



	@property
	def tracing_name(self):
		fname_data = [P.participant_id, P.block_number, P.trial_number, now(True, "%Y-%m-%d"), P.session_number]
		return "p{0}_s{4}_b{1}_t{2}_{3}.tlt".format(*fname_data)









