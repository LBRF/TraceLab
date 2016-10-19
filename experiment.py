# "fixate" at draw start; show image (maintain "fixation"; draw after SOA
__author__ = "Jonathan Mulle"
import shutil, sys
sys.path.append("ExpAssets/Resources/code/")
from random import choice
from klibs.KLExceptions import TrialException
import klibs.KLParams as P
from klibs.KLUtilities import *
from klibs.KLDraw import Ellipse, Rectangle
# from klibs.KLAudio import AudioManager, AudioClip
from klibs.KLExperiment import Experiment
from TraceLabFigure import TraceLabFigure
from ButtonBar import Button, ButtonBar
from KeyFrames import KeyFrame, FrameSet
from klibs.KLMixins import BoundaryInspector
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
PP_xx_1 = "PP-00-1"
PP_xx_5 = "PP-00-5"
MI_xx_5 = "MI-00-5"
CC_xx_5 = "CC-00-5"
PP_VV_5 = "PP-VV-5"
PP_RR_5 = "PP-RR-5"
PP_VR_5 = "PP-VR-5"
EXP_CONDITIONS = [PP_xx_1, PP_xx_5, MI_xx_5, CC_xx_5, PP_VV_5, PP_RR_5, PP_VR_5]

class TraceLab(Experiment, BoundaryInspector):

	# session vars
	p_dir = None
	fig_dir = None
	training_session = None
	session_type = None
	feedback = False
	lab_jacking = True
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
	show_drawing = True
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

	def setup(self):
		if not P.capture_figures_mode:
			if self.lab_jacking and P.exp_condition != MI_xx_5:
				self.lab_jacking = False
			if self.lab_jacking:
				self.lj = u3.U3()
				self.lj.getCalibrationData()
				self.lj_codes = {
				"baseline": u3.DAC0_8(self.lj.voltageToDACBits(0.0, dacNumber=0, is16Bits=False)),
				"origin_red_on_code": u3.DAC0_8(self.lj.voltageToDACBits(P.origin_red_on_code, dacNumber=0, is16Bits=False)),
				"origin_green_on_code": u3.DAC0_8(self.lj.voltageToDACBits(P.origin_green_on_code, dacNumber=0, is16Bits=False)),
				"origin_off_code": u3.DAC0_8(self.lj.voltageToDACBits(P.origin_off_code, dacNumber=0, is16Bits=False))}
				self.lj.getFeedback(self.lj_codes['baseline'])
		self.loading_msg = self.message("Loading...", "default", blit=False)
		self.fill()
		self.blit(self.loading_msg, 5, P.screen_c)
		self.flip()
		self.origin_size = P.origin_size
		if P.capture_figures_mode:
			self.fig_dir = os.path.join(P.resources_dir, "figures")
		else:
			self.p_dir = os.path.join(P.data_path, "p{0}_{1}".format(P.user_data[0], P.user_data[-2]))
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
		self.text_manager.add_style('instructions', 18, [255, 255, 255, 255])
		self.text_manager.add_style('error', 18, [255, 0, 0, 255])
		self.text_manager.add_style('tiny', 12, [255, 255,255, 255])
		self.text_manager.add_style('small', 14, [255, 255,255, 255])

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
		if P.exp_condition in [PP_xx_5, PP_xx_1, PP_RR_5, PP_VR_5, PP_VV_5]:
			instructions_file = instructions_file.format("physical")
		elif P.exp_condition == MI_xx_5:
			instructions_file = instructions_file.format("imagery")
		else:
			instructions_file = instructions_file.format("control")
		instructions_file = os.path.join(P.resources_dir, "Text", instructions_file)
		self.instructions = self.message(open(instructions_file).read(), "instructions", blit=False)
		self.control_fail_msg = self.message("Please keep your finger on the start area for the complete duration.", 'error', blit=False )
		self.next_trial_msg = self.message(P.next_trial_message, 'default', blit=False)
		self.next_trial_box = Rectangle(300, 75, (2, (255,255,255)))
		self.next_trial_button_loc = (Params.screen_c[0], Params.screen_c[1] - 50)
		xy_1 = (self.next_trial_button_loc[0] - 150, self.next_trial_button_loc[1] - 33)
		xy_2 = (self.next_trial_button_loc[0] + 150, self.next_trial_button_loc[1] + 33)
		self.add_boundary("next trial button", (xy_1, xy_2), RECT_BOUNDARY)

		#####
		# practice session vars & elements
		#####

		if P.exp_condition in [PP_xx_5, PP_xx_1, PP_RR_5, PP_VR_5, PP_VV_5] or P.session_number == 5:
			key_frames_f = "physical_key_frames"
		elif P.exp_condition == MI_xx_5:
			key_frames_f = "imagery_key_frames"
		else:
			key_frames_f = "control_key_frames"

		self.practice_kf = FrameSet(self, key_frames_f, "assets")
		self.practice_instructions = self.message(P.practice_instructions, "instructions", blit=False)
		practice_buttons = [('Replay', [200,100], self.practice), ('Practice', [200,100], self.__practice__),\
							('Begin', [200,100], self.any_key)]
		self.practice_button_bar = ButtonBar(self, practice_buttons, [200, 100], P.btn_s_pad, P.y_pad, finish_button=False)

		# import figures for use during testing sessions
		self.fill()
		self.blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		self.flip()
		for f in P.figures:
			self.ui_request()
			self.test_figures[f] = TraceLabFigure(self, os.path.join(P.resources_dir, "figures", f))

		if P.exp_condition in [PP_RR_5, PP_VR_5]:
			self.feedback = True
		self.clear()
		if P.enable_practice:
			if P.session_number == 1 or (P.exp_condition in [MI_xx_5, CC_xx_5] and P.session_number == 5):
				self.message(P.practice_instructions, "instructions", registration=5, location=P.screen_c, blit=True)
				self.flip()
				self.any_key()
				self.practice()

	def block(self):
		self.fill()
		self.blit(self.instructions, registration=5, location=P.screen_c, flip_x=P.flip_x)
		self.flip()
		self.any_key()

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
		self.fill()
		if self.training_session:
			self.blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		self.flip()
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
		self.fill()
		self.blit(self.next_trial_box, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		self.blit(self.next_trial_msg, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		self.flip()
		flush()
		next_trial_button_clicked = False
		if P.demo_mode:
			show_mouse_cursor()
		while not next_trial_button_clicked:
			for e in pump(True):
				if e.type == sdl2.SDL_MOUSEBUTTONDOWN:
					next_trial_button_clicked = self.within_boundary("next trial button", [e.button.x, e.button.y])
		if P.demo_mode:
			hide_mouse_cursor()

	def trial(self):
		self.figure.animate()
		self.animate_finish = P.clock.trial_time
		try:
			if P.exp_condition in (PP_xx_5, PP_xx_1, PP_VV_5, PP_VR_5, PP_RR_5):
				self.physical_trial()
			if P.exp_condition == MI_xx_5:
				if P.session_number == 5:
					self.physical_trial()
				else:
					self.imagery_trial()
			if P.exp_condition == CC_xx_5:
				if P.session_number == 5:
					self.physical_trial()
				else:
					self.control_trial()
		except TrialException as e:
			self.fill()
			self.message(P.trial_error_msg, "error")
			self.any_key()
			raise TrialException(e.message)
		self.fill()
		self.flip()

		if not P.practicing and self.lab_jacking:
			self.lj.getFeedback(self.lj_codes['origin_off_code'])
			if self.lj_spike_interval: time.sleep(self.lj_spike_interval)
			self.lj.getFeedback(self.lj_codes['baseline'])

		if self.__practicing__:
			return

		return {
			"block_num": P.block_number,
			"trial_num": P.trial_number,
			"session_num": P.session_number,
			"condition": P.exp_condition,
			"figure_type": self.figure_name,
			"figure_file": self.figure.file_name,
			"stimulus_gt": self.animate_time,
			"stimulus_mt": self.figure.animate_time,
			"avg_velocity": self.figure.avg_velocity,
			"path_length": self.figure.path_length,
			"trace_file": self.tracing_name if P.exp_condition in (PP_xx_5, PP_xx_1, PP_VV_5, PP_VR_5, PP_RR_5) else NA,
			"rt": self.rt,
			"it": self.it,
			"control_question": self.control_question if P.exp_condition == CC_xx_5 else NA,
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
		q_str = "UPDATE `sessions` SET `sessions_completed` = ? WHERE `id` = ?"
		self.database.query(q_str, QUERY_UPD, q_vars = [P.session_number, P.participant_id])

	def display_refresh(self, flip=True):
		self.fill()
		origin = self.origin_active  if self.rc.draw_listener.active else self.origin_inactive
		self.blit(origin, 5, self.origin_pos, flip_x=P.flip_x)
		if self.show_drawing:
			try:
				drawing = self.rc.draw_listener.render_progress()
				self.blit(drawing, 5, P.screen_c, flip_x=P.flip_x)
			except TypeError:
				pass
		if flip:
			self.flip()

	def init_session(self, id_str=None):
		session_data_str = "SELECT * FROM `sessions` WHERE `participant_id` = ?"
		if id_str:
			try:
				userhash = sha1(id_str).hexdigest()
				user_data_str = "SELECT * FROM `participants` WHERE `userhash` = ?"
				user_data = self.database.query(user_data_str, q_vars=[userhash]).fetchall()[0]
				P.participant_id = user_data[0]
				P.random_seed = str(user_data[2])
				session_data = self.database.query(session_data_str, q_vars=[P.participant_id]).fetchall()[0]
				P.session_id = session_data[0]
				P.exp_condition = session_data[2]
				P.session_number = session_data[3] + 1
			except IndexError:
				retry = self.query("That identifier wasn't found. Do you wish to try another? (y)es or (n)o",
								   accepted=['y', 'Y', 'n', 'N'], flip_x=P.flip_x)
				if retry == 'y':
					return self.collect_demographics()
				else:
					self.fill()
					self.message("Thanks for participating!", location=P.screen_c, flip_x=P.flip_x)
					self.flip()
					self.any_key()
					self.quit()
		else:
			P.session_number = 1
			q_str = "SELECT * FROM `participants` WHERE `id` = ?"
			user_data = self.database.query(q_str, q_vars=[P.participant_id]).fetchall()[0]
		P.user_data = user_data

		# delete previous trials for this session if any exist (essentially assume a do-
		if not P.capture_figures_mode:
			q_str = "DELETE FROM `trials` WHERE `participant_id` = ? AND `session_num` = ?"
			self.database.query(q_str, q_vars=[P.participant_id, P.session_number])
			if P.session_number == 1:
				try:
					 session_data = self.database.query(session_data_str, q_vars=[P.participant_id]).fetchall()[0]
					 P.exp_condition = session_data[2]
				except IndexError:
					P.exp_condition = self.query("Enter an experimental condition identifier:", accepted=EXP_CONDITIONS, flip_x=P.flip_x)
					self.database.init_entry('sessions')
					self.database.log('participant_id', P.participant_id)
					self.database.log('sessions_completed', 0)
					self.database.log('exp_condition', P.exp_condition)
					P.session_id = self.database.insert()
			self.training_session = P.session_number not in (1,5)
			self.session_type = "training" if self.training_session else "testing"
		else:
			self.training_session = True
			self.session_type = "figure_capture"
			P.session_id = -1
		P.demographics_collected = True

	def imagery_trial(self):
		self.fill()
		self.blit(self.origin_inactive, 5, self.origin_pos, flip_x=P.flip_x)
		self.flip()		
		if not P.practicing and self.lab_jacking:
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
			self.ui_request()

		self.fill()
		self.blit(self.origin_active, 5, self.origin_pos, flip_x=P.flip_x)
		self.flip()
		if not P.practicing and self.lab_jacking:
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
		if self.feedback and not self.__practicing__:
			flush()
			self.fill()
			self.blit(self.figure.render(trace=self.drawing), 5, Params.screen_c, flip_x=P.flip_x)
			self.flip()
			start = time.time()
			while time.time() - start < Params.max_feedback_time / 1000.0:
				self.ui_request()

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
			self.fill()
			self.message("Press command+q at any time to exit.\nPress any key to continue.", "default", registration=5, location=P.screen_c, flip=True)
			self.any_key()
			finished = False
		else:
			self.fill()
			msg = "Quitting (command+q) may be unresponsive during autogeneration.\n" \
				  "Use the program 'ActivityMonitor' to kill ALL Python processes.\n" \
				  "TraceLab will automatically exit when figure generation is complete.\n \n" \
				  "Press any key to begin generating."
			self.message(msg, "default", registration=5, location=P.screen_c, flip=True)
			self.any_key()
			finished = self.auto_generate_count == 0
		io_errors = []
		while not finished:
			try:
				finished = self.__review_figure__()
			except IOError:
				io_errors.append((P.auto_generate_count + 1) - self.auto_generate_count)
				if len(io_errors) > 10:
					print "\n".join(io_errors)
					break
		self.quit()

	def __review_figure__(self):
		self.fill()
		if P.auto_generate:
			msg = "Generating figure {0} of {1}".format((P.auto_generate_count + 1) - self.auto_generate_count, P.auto_generate_count)
			self.message(msg, "default", registration=5, location=P.screen_c, flip=True)

		while not self.figure:
			self.ui_request()
			try:
				self.figure = TraceLabFigure(self)
			except RuntimeError:
				pass
		self.animate_time = 5000.0
		self.figure.render()
		self.figure.prepare_animation()
		if not P.auto_generate:
			self.figure.animate()
			self.flip()
			self.any_key()
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
				self.fill()
				self.message("Saving... ", flip=True)
				self.figure.write_out(f_name)

		if P.auto_generate:
			self.auto_generate_count -= 1
			self.figure.write_out("template_{0}.tlf".format(time.time()))
			if self.auto_generate_count == 0:
				return True

	def practice(self, play_key_frames=True, callback=None):
		self.__practicing__ = True

		if callback == self.__practice__:
			play_key_frames = False
			self.__practice__()
		elif callback == self.practice:
			play_key_frames = True
		elif callback == self.any_key:
			self.__practicing__ = False
			return self.any_key()

		if play_key_frames:
			self.practice_kf.play()

		self.practice_button_bar.reset()
		self.practice_button_bar.render()
		P.clock.start()
		cb = self.practice_button_bar.collect_response()
		P.clock.stop()

		self.__practicing__ = False

		return self.practice(callback=cb)

		# reset stuff before the experiment proper begins

	def __practice__(self):
		self.figure_name = P.practice_figure
		self.animate_time = P.practice_animation_time
		self.setup_response_collector()
		self.trial_prep()
		P.clock.start()
		self.trial()
		P.clock.stop()
		self.trial_clean_up()



	@property
	def tracing_name(self):
		fname_data = [P.participant_id, P.block_number, P.trial_number, now(True, "%Y-%m-%d"), P.session_number]
		return "p{0}_s{4}_b{1}_t{2}_{3}.tlt".format(*fname_data)









