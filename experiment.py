# "fixate" at draw start; show image (maintain "fixation"; draw after SOA
__author__ = "Jonathan Mulle"
import imp, sys, shutil, os
sys.path.append("ExpAssets/Resources/code/")
from klibs.KLExceptions import TrialException
from klibs.KLConstants import *
import klibs.KLParams as P
from klibs.KLUtilities import *
from klibs.KLDraw import Ellipse
from klibs.KLEventInterface import EventTicket as ET
from klibs.KLExperiment import Experiment
from TraceLabFigure import TraceLabFigure
from Slider import Slider
from klibs.KLMixins import BoundaryInspector
from hashlib import sha1

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

	# graphical elements
	value_slider = None
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

	instructions = None
	loading_msg = None
	control_fail_msg = None
	next_trial_msg = None
	response_window_extension = 1 # second
	response_window = None  # animate_time + constant

	# debug & configuration
	show_drawing = True
	sample_exposure_time = 4500

	# dynamic trial vars
	boundaries = {}
	use_random_figures = False
	drawing = []
	drawing_name = None
	rt = None  # time to initiate responding post-stimulus
	mt = None  # time to complete response
	mode = None
	seg_estimate = None
	test_figures = {}
	figure = None
	figure_dots = None
	figure_segments = None

	# configured trial factors (dynamically loaded per-trial
	animate_time = None
	figure_name = None


	def __init__(self, *args, **kwargs):
		super(TraceLab, self).__init__(*args, **kwargs)
		P.flip_x=False

	def setup(self):
		self.origin_size = P.origin_size
		try:
			self.p_dir = os.path.join(P.data_path, "p{0}_{1}".format(P.user_data[0], P.user_data[-2]))
			self.fig_dir = os.path.join(self.p_dir, self.session_type, "session_" + str(P.session_number))
			if os.path.exists(self.fig_dir):
				shutil.rmtree(self.fig_dir)
			os.makedirs(self.fig_dir)
		except AttributeError:  # for capture-figure mode
			self.fig_dir = os.path.join(P.resources_dir, "figures")

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
		self.value_slider = Slider(self, int(P.screen_y * 0.75), int(P.screen_x * 0.5), 15, 20, (75,75,75), RED)
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
		self.loading_msg = self.message("Loading...", "default", blit=False)
		self.control_fail_msg = self.message("Please keep your finger on the start area for the complete duration.", 'error', blit=False )
		self.next_trial_msg = self.message("Press any key to begin the trial.", 'default', blit=False)

		# import figures for use during testing sessions
		self.fill()
		self.blit(self.loading_msg, 5, P.screen_c, flip_x=P.flip_x)
		self.flip()
		for f in P.figures:
			self.ui_request()
			self.test_figures[f] = TraceLabFigure(self, os.path.join(P.resources_dir, "figures", f))
		if P.exp_condition in [PP_RR_5, PP_VR_5]:
			self.feedback = True

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
		self.rt = -1.0
		self.animate_time = int(self.animate_time)
		self.drawing = NA
		self.seg_estimate = -1
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
		self.origin_pos = list(self.figure.frames[0])
		if P.flip_x:
			self.origin_pos[0] = P.screen_x - self.origin_pos[0]
		self.add_boundary("origin", [self.origin_pos, self.origin_size // 2], CIRCLE_BOUNDARY)
		self.origin_boundary = [self.origin_pos, self.origin_size // 2]
		self.rc.draw_listener.add_boundaries([('start', self.origin_boundary, CIRCLE_BOUNDARY),
											  ('stop', self.origin_boundary, CIRCLE_BOUNDARY)])
		if P.demo_mode:
			self.figure.render()
		self.value_slider.update_range(self.figure.seg_count)
		self.figure.prepare_animation()
		# let participant self-initiate next trial
		self.fill()
		self.blit(self.next_trial_msg, 5, P.screen_c, flip_x=P.flip_x)
		self.flip()
		self.any_key()

	def trial(self):
		self.figure.animate()
		if P.exp_condition == MI_xx_5:
			self.imagery_trial()
		if P.exp_condition in (PP_xx_5, PP_xx_1, PP_VV_5, PP_VR_5, PP_RR_5):
			self.physical_trial()
		if P.exp_condition == CC_xx_5:
			self.control_trial()
		self.fill()
		self.flip()

		return {
			"block_num": P.block_number,
			"trial_num": P.trial_number,
			"session_num": P.session_number,
			"condition": P.exp_condition,
			"figure_file": self.figure.file_name if self.training_session else self.figure_name,
			"stimulus_gt": self.animate_time,
			"stimulus_mt": self.figure.animate_time,
			"avg_velocity": self.figure.avg_velocity,
			"path_length": self.figure.path_length,
			"trace_file": self.tracing_name if P.exp_condition != CC_xx_5 else NA,
			"rt":  self.rt,
			"seg_count": self.figure.seg_count,
			"seg_estimate": self.seg_estimate,
			"mt": self.mt,
		}

	def trial_clean_up(self):
		self.value_slider.reset()
		self.figure.write_out()
		self.figure.write_out(self.tracing_name, self.drawing)

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
		P.demographics_collected = True

	def imagery_trial(self):
		self.fill()
		self.blit(self.origin_inactive, 5, self.origin_pos, flip_x=P.flip_x)
		self.flip()
		P.tk.start("imaginary trace")
		if P.demo_mode:
			show_mouse_cursor()
		at_origin = False
		while not at_origin:
			for e in pump(True):
				if e.type == sdl2.SDL_MOUSEBUTTONDOWN:
					click_loc = (e.button.x, e.button.y)
					at_origin = self.within_boundary('origin',click_loc)
			if self.within_boundary('origin', mouse_pos()):
				at_origin = True
				self.ui_request(e)
			# self.ui_request()
		self.fill()
		self.blit(self.origin_active, 5, self.origin_pos, flip_x=P.flip_x)
		self.flip()
		while at_origin:
			for e in pump(True):
				if e.type == sdl2.SDL_MOUSEBUTTONUP:
					at_origin = False
				self.ui_request(e)
			if not self.within_boundary('origin', mouse_pos()):
			 	at_origin = False
		mt =  P.tk.stop("imaginary trace").read("imaginary trace")
		self.mt = mt[1] - mt[0]
		if P.demo_mode:
			hide_mouse_cursor()

	def physical_trial(self):
		start = P.clock.trial_time
		self.rc.collect()
		self.rt = self.rc.draw_listener.start_time - start
		self.drawing = self.rc.draw_listener.responses[0][0]
		self.mt = self.rc.draw_listener.responses[0][1] - self.rt
		if self.feedback:
			flush()
			self.fill()
			self.blit(self.figure.render(trace=self.drawing), 5, Params.screen_c, flip_x=P.flip_x)
			self.flip()
			start = time.time()
			while time.time() - start > Params.max_feedback_time:
				self.ui_request()

	def control_trial(self):
		self.drawing = NA
		P.tk.start("seg estimate")
		while self.seg_estimate == -1:
			self.seg_estimate = self.value_slider.slide()
		mt = P.tk.stop("seg estimate").read("seg estimate")
		self.mt = mt[1] - mt[0]

	def capture_figures(self):
		self.animate_time = 5000.0
		self.fill()
		self.message("Press command+q at any time to exit.\nPress any key to continue.", "default", registration=5, location=P.screen_c, flip=True)
		self.any_key()
		finished = False
		while not finished:
			finished = self.__review_figure()
		self.quit()

	def __review_figure(self):
		self.fill()
		while not self.figure:
			self.ui_request()
			try:
				self.figure = TraceLabFigure(self)
			except RuntimeError:
				pass
		self.animate_time = 5000.0
		self.figure.render()
		self.figure.prepare_animation()
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
			self.fill()
			self.message("Saving... ", flip=True)
			f_name = sha1("figure_" + str(now(True))).hex_digest() + ".tlf"
			self.figure.write_out(f_name)


	@property
	def tracing_name(self):
		fname_data = [P.participant_id, P.block_number, P.trial_number, now(True, "%Y-%m-%d"), P.session_number]
		return "p{0}_s{4}_b{1}_t{2}_{3}.tlt".format(*fname_data)









