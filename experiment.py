# "fixate" at draw start; show image (maintain "fixation"; draw after SOA
__author__ = "Jonathan Mulle"
import shutil, sys

sys.path.append("ExpAssets/Resources/code/")
from sdl2 import SDL_MOUSEBUTTONDOWN
from random import choice
from os.path import join, exists
from os import makedirs
from operator import  sub

from klibs.KLExceptions import TrialException
from klibs import P
from klibs.KLConstants import NA, RC_DRAW, RECT_BOUNDARY, CIRCLE_BOUNDARY, STROKE_OUTER, QUERY_UPD
from klibs.KLUtilities import *
from klibs.KLUtilities import colored_stdout as cso
from klibs.KLGraphics import blit, fill, flip, clear
from klibs.KLGraphics.KLDraw import Ellipse, Rectangle
from klibs.KLCommunication import message, query
from klibs.KLUserInterface import any_key, ui_request, konami_code
from klibs.KLTime import CountDown
from klibs.KLExperiment import Experiment
from TraceLabFigure import TraceLabFigure
from klibs.KLBoundary import BoundaryInspector

from ButtonBar import Button, ButtonBar
from KeyFrames import KeyFrame, FrameSet
from TraceLabSession import TraceLabSession

try:
	import u3
except ImportError:
	pass

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
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
SESSION_FIG = "figure_capture"
SESSION_TRN = "training"
SESSION_TST = "testing"
LEFT_HANDED = "l"
RIGHT_HANDED = "r"

class TraceLab(Experiment, BoundaryInspector):
	# session vars
	p_dir = None
	fig_dir = None
	session = None
	session_number = None
	training_session = None
	session_type = None
	exp_condition = None
	session_count = None
	feedback_type = False
	handedness = None
	created = None
	practice_session = False  # ie. this session should include the practice display
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
	handedness = None
	loading_msg = None
	control_fail_msg = None
	next_trial_msg = None
	next_trial_box = None
	next_trial_button_loc = None
	next_trial_button_bounds = None
	response_window_extension = 1  # second
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
	figure_sets = {}   # complete set of available figure sets
	figure_set = []  # figure set currently in use for this participant
	figure_key = None  # key for current figure set

	# practice stuff
	narration = None
	__practicing__ = False
	practice_buttons = None
	practice_instructions = None
	practice_button_bar = None
	practice_kf = None

	intertrial_start = None
	intertrial_end = None
	intertrial_timing_logs = {}

	def __init__(self, *args, **kwargs):
		super(TraceLab, self).__init__(*args, **kwargs)
		P.flip_x = P.mirror_mode

	def __practice__(self):
		self.figure_name = P.practice_figure
		self.animate_time = P.practice_animation_time
		self.setup_response_collector()
		self.trial_prep()
		self.evm.start_clock()
		try:
			self.trial()
		except:
			pass
		self.evm.stop_clock()
		self.trial_clean_up()

	def __review_figure__(self):
		fill()
		if P.auto_generate:
			msg = "Generating figure {0} of {1}".format((P.auto_generate_count + 1) - self.auto_generate_count,
														P.auto_generate_count)
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
		self.txtm.add_style('instructions', 18, [255, 255, 255, 255])
		self.txtm.add_style('error', 18, [255, 0, 0, 255])
		self.txtm.add_style('tiny', 12, [255, 255, 255, 255])
		self.txtm.add_style('small', 14, [255, 255, 255, 255])
		self.session = TraceLabSession()
		self.trial_factory.dump()
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
			self.p_dir = os.path.join(P.data_dir, "p{0}_{1}".format(P.participant_id, self.created))
			self.fig_dir = os.path.join(self.p_dir, self.session_type, "session_" + str(self.session_number))
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

		if P.capture_figures_mode:
			self.capture_figures()

		btn_vars = ([(str(i), P.btn_size, None) for i in range(1, 6)], P.btn_size, P.btn_s_pad, P.y_pad, P.btn_instrux)
		self.button_bar = ButtonBar(*btn_vars)
		self.use_random_figures = self.session_number not in (1, 5)
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
		self.control_fail_msg = message("Please keep your finger on the start area for the complete duration.", 'error',
										blit_txt=False)
		self.next_trial_msg = message(P.next_trial_message, 'default', blit_txt=False)
		self.next_trial_box = Rectangle(300, 75, (2, (255, 255, 255)))
		self.next_trial_button_loc = (250 if self.handedness == LEFT_HANDED else P.screen_x - 250, P.screen_y - 100)
		xy_1 = (self.next_trial_button_loc[0] - 150, self.next_trial_button_loc[1] - 33)
		xy_2 = (self.next_trial_button_loc[0] + 150, self.next_trial_button_loc[1] + 33)
		self.add_boundary("next trial button", (xy_1, xy_2), RECT_BOUNDARY)

		#####
		# prac BBB                                                                                 QDW                                                                                                                                                                                          BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBVVVVVVVVVVVVVVVVVVVVVVVVVVVV                                                         tice session vars & elements
		#####
		if self.exp.practice_session:
			if (self.exp_condition == PHYS and self.session_number == 1) or (
					self.session_number == self.session_count and self.exp_condition != PHYS):
				key_frames_f = "physical_key_frames"
			elif self.exp_condition == MOTR and self.session_number == 1:
				key_frames_f = "imagery_key_frames"
			elif self.session_number == 1:
				key_frames_f = "control_key_frames"

			self.practice_kf = FrameSet(self, key_frames_f, "assets")
			self.practice_instructions = message(P.practice_instructions, "instructions", blit_txt=False)
			practice_buttons = [('Replay', [200, 100], self.practice), ('Practice', [200, 100], self.__practice__), \
								('Begin', [200, 100], any_key)]
			self.practice_button_bar = ButtonBar(practice_buttons, [200, 100], P.btn_s_pad, P.y_pad,
												 finish_button=False)

		# import figures for use during testing sessions
		fill()
		blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		flip()
		for f in P.figures:
			ui_request()
			self.test_figures[f] = TraceLabFigure(os.path.join(P.resources_dir, "figures", f))

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
		# self.rc.end_collection_event = 'response_period_end'
		self.rc.draw_listener.start_boundary = 'start'
		self.rc.draw_listener.stop_boundary = 'stop'
		self.rc.draw_listener.show_active_cursor = False
		self.rc.draw_listener.show_inactive_cursor = True
		self.rc.draw_listener.origin = self.origin_pos
		self.rc.draw_listener.interrupts = True
		self.rc.display_callback = self.display_refresh
		self.rc.display_callback_args = [True]
		if P.dm_always_show_cursor:
			self.rc.draw_listener.show_active_cursor = True
			self.rc.draw_listener.show_inactive_cursor = True
		if P.demo_mode or self.feedback_type in (FB_DRAW, FB_ALL):
			self.rc.draw_listener.render_real_time = True

	def trial_prep(self):
		self.log("\n\n********** TRIAL {0} ***********\n".format(P.trial_number))
		self.control_question = choice(["LEFT", "RIGHT", "UP", "DOWN"])
		self.rt = 0.0
		self.it = 0.0
		self.animate_time = int(self.animate_time)
		self.drawing = NA
		self.control_response = -1
		fill()
		blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		flip()
		failed_generations = 0
		self.figure = None
		if self.figure_name == "random":
			while not self.figure:
				try:
					self.figure = TraceLabFigure()
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

		#  now that prep is finished, start the intertrial interval calculation
		if self.intertrial_start:
			self.intertrial_end = time.time()
			intertrial_interval = self.intertrial_end - self.intertrial_start
			self.log_f.write(str(intertrial_interval) + "\n")
			if intertrial_interval > P.intertrial_rest_interval:
				cso("\t<red>Warning: trial preparation for this trial exceeded intertrial rest interval.</red>")
			else:
				inter_trial_rest = CountDown(P.intertrial_rest_interval - intertrial_interval)
				while inter_trial_rest.counting():
					ui_request()
		if P.trial_number > 1:
			self.log("t{0}_intertrial_interval_end".format(P.trial_number - 1), True)
			self.log("write_out")
		self.log("t{0}_intertrial_interval_start".format(P.trial_number), True)
		self.intertrial_start = time.time()

		# let participant self-initiate next trial
		fill()
		blit(self.next_trial_box, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		blit(self.next_trial_msg, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		flip()
		flush()
		next_trial_button_clicked = False
		if P.demo_mode or P.dm_always_show_cursor:
			show_mouse_cursor()

		while not next_trial_button_clicked:
			event_queue = pump(True)
			for e in event_queue:
				if e.type == SDL_MOUSEBUTTONDOWN:
					next_trial_button_clicked = self.within_boundary("next trial button", [e.button.x, e.button.y])
				ui_request(e)
		if P.demo_mode or P.dm_always_show_cursor:
			hide_mouse_cursor()

	def trial(self):
		self.figure.animate()
		self.animate_finish = self.evm.trial_time
		try:
			if self.exp_condition == PHYS or self.session_number == self.session_count:
				self.physical_trial()
			elif self.exp_condition == MOTR:
				self.imagery_trial()
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
			"session_num": self.session_number,
			"exp_condition": self.exp_condition,
			"figure_type": self.figure_name,
			"figure_file": self.figure.file_name,
			"stimulus_gt": self.animate_time,
			"stimulus_mt": self.figure.animate_time,
			"avg_velocity": self.figure.avg_velocity,
			"path_length": self.figure.path_length,
			"trace_file": self.tracing_name if self.exp_condition == PHYS else NA,
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
		if self.session_number == self.session_count and P.enable_learned_figures_querying:
			from klibs.KLCommunication import user_queries
			self.fig_dir =  join(self.p_dir, "learned")
			if not exists(self.fig_dir):
				makedirs(self.fig_dir)

			learned_fig_num = 1
			if query(user_queries.experimental[5]) == "y":
				while True:
					self.capture_learned_figure(learned_fig_num)
					if query(user_queries.experimental[6]) == "y":
						learned_fig_num += 1
					else:
						break

		# if the entire experiment is successfully completed, update the sessions_completed column
		q_str = "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?"
		self.db.query(q_str, QUERY_UPD, q_vars=[self.session_number, P.participant_id])
		self.db.insert([P.participant_id, self.session_number, now(True)], "sessions")
		fill()
		message(P.experiment_complete_message, "instructions", registration=5, location=P.screen_c, flip_screen=True)
		any_key()

	def display_refresh(self, flip_screen=True):
		fill()
		origin = self.origin_active if self.rc.draw_listener.active else self.origin_inactive
		blit(origin, 5, self.origin_pos, flip_x=P.flip_x)
		if P.dm_render_progress or self.feedback_type in (FB_ALL, FB_DRAW):
			try:
				drawing = self.rc.draw_listener.render_progress()
				blit(drawing, 5, P.screen_c, flip_x=P.flip_x)
			except TypeError:
				pass
		if flip_screen:
			flip()

	def imagery_trial(self):
		fill()
		blit(self.origin_inactive, 5, self.origin_pos, flip_x=P.flip_x)
		flip()
		if not P.practicing and P.labjacking:
			self.lj.getFeedback(self.lj_codes['origin_red_on_code'])
			if self.lj_spike_interval:
				time.sleep(self.lj_spike_interval)
			self.lj.getFeedback(self.lj_codes['baseline'])
		start = self.evm.trial_time
		if P.demo_mode or P.dm_always_show_cursor:
			show_mouse_cursor()
		at_origin = False
		while not at_origin:
			if self.within_boundary('origin', mouse_pos()):
				at_origin = True
				self.rt = self.evm.trial_time - start
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
		self.mt = self.evm.trial_time - (self.rt + start)
		if P.demo_mode:
			hide_mouse_cursor()

	def physical_trial(self):
		start = self.evm.trial_time
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
		if P.dm_always_show_cursor:
			show_mouse_cursor()
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
			message("Press command+q at any time to exit.\nPress any key to continue.", "default", registration=5,
					location=P.screen_c, flip=True)
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

	def capture_learned_figure(self, fig_number):
		self.evm.start_clock()
		fig_name = "p{0}_learned_figure_{1}.tlt".format(P.participant_id, fig_number)
		self.rc.draw_listener.reset()
		self.rc.collect()
		self.figure.write_out(fig_name, self.rc.draw_listener.responses[0][0])
		self.evm.stop_clock()

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
		self.evm.start_clock()
		cb = self.practice_button_bar.collect_response()
		self.evm.stop_clock()

		self.__practicing__ = False

		return self.practice(callback=cb)

	def log(self, msg, t=None):
		if P.use_log_file:
			if msg != "write_out":
				if t:
					self.intertrial_timing_logs[msg] = time.time()
				else:
					self.log_f.write(msg)
			else:
				ivi_start = self.intertrial_timing_logs['t{0}_intertrial_interval_start'.format(P.trial_number - 1)]
				ivi_end = self.intertrial_timing_logs['t{0}_intertrial_interval_end'.format(P.trial_number - 1)]
				self.log_f.write(str_pad("intertrial_interval" + ":", 32) + str(ivi_end - ivi_start) + "\n")

	def quit(self):
		self.log_f.close()
		super(TraceLab, self).quit()

	@property
	def tracing_name(self):
		fname_data = [P.participant_id, P.block_number, P.trial_number, now(True, "%Y-%m-%d"), self.session_number]
		return "p{0}_s{4}_b{1}_t{2}_{3}.tlt".format(*fname_data)
