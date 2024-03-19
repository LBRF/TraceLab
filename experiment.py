# -*- coding: utf-8 -*-
__author__ = "Jonathan Mulle"

import os
import io
import time

from random import choice
from sdl2 import SDL_MOUSEBUTTONDOWN, SDL_KEYDOWN

import klibs
from klibs import P
from klibs.KLConstants import RECT_BOUNDARY, CIRCLE_BOUNDARY, STROKE_OUTER, QUERY_UPD
from klibs.KLBoundary import BoundaryInspector
from klibs.KLTime import CountDown
from klibs.KLUserInterface import any_key, ui_request
from klibs.KLUtilities import (pump, flush, scale, now, mouse_pos,
	show_mouse_cursor, hide_mouse_cursor, utf8)
from klibs.KLUtilities import colored_stdout as cso
from klibs.KLGraphics import blit, fill, flip
from klibs.KLGraphics.KLDraw import Ellipse, Rectangle
from klibs.KLCommunication import user_queries, message, query
from klibs.KLResponseCollectors import DrawResponse

from TraceLabSession import TraceLabSession
from TraceLabFigure import TraceLabFigure
from ButtonBar import ButtonBar
from KeyFrames import FrameSet


WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BOT_L = 0
TOP_L = 1
TOP_R = 2

# condition codes; jon hates retyping strings
PHYS = "physical"
MOTR = "imagery"
CTRL = "control"
FB_DRAW = "drawing_feedback"
FB_RES = "results_feedback"
FB_ALL = "all_feedback"
LEFT_HANDED = "l"
RIGHT_HANDED = "r"


if __name__ == "__main__":
	cso("<red>\nError: TraceLab must be run through the KLibs environment " \
		"and cannot be run directly with Python. Please run " \
		"'klibs run screensize' in the TraceLab folder to start the " \
		"experiment, replacing 'screensize' with the diagonal size " \
		"of your monitor in inches (e.g. 24).\n</red>")


class TraceLab(klibs.Experiment, BoundaryInspector):

	# session vars
	p_dir = None
	fig_dir = None
	user_id = None
	session = None
	session_structure = None
	session_number = None
	block_factors = []
	response_type = None
	prev_response_type = None
	session_count = None
	feedback_type = False
	first_trial = False
	handedness = None
	created = None
	show_practice_display = False  # ie. this session should include the practice display
	figure_sets = {}  # complete set of available figure sets
	figure_set_name = "NA"
	log_f = None

	origin_active_color = GREEN
	origin_inactive_color = RED
	origin_pos = None
	origin_boundary = None
	instructions = None
	trigger = None
	magstim = None

	# dynamic trial vars
	drawing = []
	rt = None  # time to initiate responding post-stimulus
	mt = None  # time to start and complete response
	it = None  # time between arriving at origin and intiating response (ie. between RT and MT)
	control_response = None
	test_figures = {}
	figure = None
	control_question = None  # which question the control will be asked to report an answer for

	# configured trial factors (dynamically loaded per-trial
	animate_time = None
	figure_name = None

	# practice stuff
	__practicing__ = False
	practice_buttons = None
	practice_instructions = None
	practice_button_bar = None
	practice_kf = None

	intertrial_start = None
	intertrial_end = None
	intertrial_timing_logs = {}


	def __init__(self):

		klibs.Experiment.__init__(self)
		BoundaryInspector.__init__(self)
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


	def setup(self):

		# Set up custom text styles for the experiment
		self.txtm.add_style('instructions', 18, [255, 255, 255, 255])
		self.txtm.add_style('error', 18, [255, 0, 0, 255])
		self.txtm.add_style('tiny', 12, [255, 255, 255, 255])
		self.txtm.add_style('small', 14, [255, 255, 255, 255])

		# Pre-render shape stimuli
		dot_stroke = [P.dot_stroke, P.dot_stroke_col, STROKE_OUTER] if P.dot_stroke > 0 else None
		self.tracker_dot = Ellipse(P.dot_size, stroke=dot_stroke, fill=P.dot_color).render()
		self.origin_active = Ellipse(P.origin_size, fill=self.origin_active_color).render()
		self.origin_inactive = Ellipse(P.origin_size, fill=self.origin_inactive_color).render()

		# If capture figures mode, generate, view, and optionally save some figures
		if P.capture_figures_mode:
			self.fig_dir = os.path.join(P.resources_dir, "figures")
			self.capture_figures()
			self.quit()

		# Initialize participant ID and session options, reloading ID if it already exists
		self.session = TraceLabSession()
		self.user_id = self.session.user_id

		# Once session initialized, show loading screen and finish setup
		self.loading_msg = message("Loading...", "default", blit_txt=False)
		fill()
		blit(self.loading_msg, 5, P.screen_c)
		flip()

		# Scale UI size variables to current screen resolution
		P.btn_s_pad = scale((P.btn_s_pad, 0), (1920, 1080))[0]
		P.y_pad = scale((0, P.y_pad), (1920, 1080))[1]

		# Initialize messages and response buttons for control trials
		control_fail_txt = "Please keep your finger on the start area for the complete duration."
		self.control_fail_msg = message(control_fail_txt, 'error', blit_txt=False)
		ctrl_buttons = ["1", "2", "3", "4", "5"]
		self.control_bar = ButtonBar(
			buttons = [(i, P.btn_size, None) for i in ctrl_buttons],
			button_size = P.btn_size, screen_margins = P.btn_s_pad, y_offset = P.y_pad,
			message_txt = P.control_q
		)

		# Initialize 'next trial' button
		button_x = 250 if self.handedness == LEFT_HANDED else P.screen_x - 250
		button_y = P.screen_y - 100
		self.next_trial_msg = message(P.next_trial_message, 'default', blit_txt=False)
		self.next_trial_box = Rectangle(300, 75, stroke=(2, (255, 255, 255), STROKE_OUTER))
		self.next_trial_button_loc = (button_x, button_y)
		bounds = [(button_x - 150, button_y - 38), (button_x + 150, button_y + 38)]
		self.add_boundary("next trial button", bounds, RECT_BOUNDARY)

		# Initialize instructions and practice button bar for each condition
		self.instruction_files = {
			PHYS: {'text': "physical_group_instructions.txt", 'frames': "physical_key_frames"},
			MOTR: {'text': "imagery_group_instructions.txt", 'frames': "imagery_key_frames"},
			CTRL: {'text': "control_group_instructions.txt", 'frames': "control_key_frames"}
		}
		self.practice_instructions = message(
			P.practice_instructions, "instructions",
			align="center", blit_txt=False
		)
		practice_buttons = [
			('Replay', [200, 100], self.practice),
			('Practice', [200, 100], self.__practice__),
			('Begin', [200, 100], any_key)
		]
		self.practice_button_bar = ButtonBar(
			practice_buttons,
			[200, 100], P.btn_s_pad, P.y_pad, finish_button=False
		)

		# Import all pre-generated figures needed for the current session
		figures = list(set(self.trial_factory.exp_factors["figure_name"]))
		figures.append(P.practice_figure)
		for f in figures:
			if f != "random":
				ui_request()
				fig_path = os.path.join(P.resources_dir, "figures", f)
				self.test_figures[f] = TraceLabFigure(fig_path, handedness = self.handedness)

		# Initialize trigger port (if required)
		self.trigger = None
		if P.requires_triggers:
			from communication import get_trigger_port
			self.trigger = get_trigger_port()
			self.trigger.add_codes(P.trigger_codes)

		# Initialize TMS communication (if required)
		self.magstim = None
		if P.requires_tms:
			from communication import get_tms_controller
			self.magstim = get_tms_controller()


	def block(self):

		# Get response type and feedback type for block
		self.response_type = self.block_factors[P.block_number - 1]['response_type']
		self.feedback_type = self.block_factors[P.block_number - 1]['feedback_type']

		# If on first block of session, or response type is different from response type of
		# previous block, do tutorial animation and practice
		if self.response_type != self.prev_response_type:

			# Load instructions for new response type
			new_instructions = self.instruction_files[self.response_type]
			instructions_file = os.path.join(P.resources_dir, "Text", new_instructions['text'])
			inst_txt = io.open(instructions_file, encoding='utf-8').read()
			self.instructions = message(inst_txt, "instructions", align="center", blit_txt=False)

			if P.enable_practice:
				# Load tutorial animation for current condition, play it, and enter practice
				self.practice_kf = FrameSet(new_instructions['frames'], "assets")
				if P.block_number == 1:
					fill()
					blit(self.practice_instructions, 5, P.screen_c)
					flip()
					any_key()
				else:
					self.start_trial_button()
				self.practice()

			self.prev_response_type = self.response_type

		for i in range(1,4):
			# we do this a few times to avoid block messages being skipped due to duplicate input
			# from the touch screen we use
			ui_request()
			fill()
			blit(self.instructions, registration=5, location=P.screen_c, flip_x=P.flip_x)
			flip()
		any_key()

		# Indicates if on first trial of block, needed for reloading incomplete sessions
		self.first_trial = True


	def setup_response_collector(self):

		self.rc.uses(DrawResponse)
		self.rc.terminate_after = [120, klibs.TK_S] # Wait really long before timeout
		self.rc.draw_listener.start_boundary = 'start'
		self.rc.draw_listener.stop_boundary = 'stop'
		self.rc.draw_listener.show_active_cursor = False
		self.rc.draw_listener.show_inactive_cursor = True
		self.rc.draw_listener.origin = self.origin_pos
		self.rc.draw_listener.interrupts = True
		self.rc.draw_listener.min_samples = 5
		self.rc.display_callback = self.display_refresh

		if P.dm_always_show_cursor:
			self.rc.draw_listener.show_active_cursor = True
			self.rc.draw_listener.show_inactive_cursor = True

		if P.demo_mode or self.feedback_type in (FB_DRAW, FB_ALL):
			self.rc.draw_listener.render_real_time = True


	def trial_prep(self):

		# If reloading incomplete block, update trial number accordingly
		if self.first_trial:
			trials_in_block = len(self.blocks.blocks[P.block_number - 1])
			P.trial_number = (P.trials_per_block - trials_in_block) + 1
			self.first_trial = False

		# Initialize/reset trial variables before beginning trial
		self.control_question = choice(["LEFT", "RIGHT", "UP", "DOWN"])
		self.rt = 0.0
		self.it = 0.0
		self.animate_time = int(self.animate_time)
		self.drawing = 'NA'
		self.control_response = -1
		self.figure = None

		# Either load a pre-generated figure or generate a new one, depending on trial
		if self.figure_name == "random":
			self.figure = self._generate_figure(duration=self.animate_time)
		else:
			self.figure = self.test_figures[self.figure_name]
			self.figure.animate_target_time = self.animate_time
			self.figure.render()
			self.figure.prepare_animation()

		# Initialize origin position and origin boundaries based on the loaded figure
		self.origin_pos = list(self.figure.points[0])
		if P.flip_x:
			self.origin_pos[0] = P.screen_x - self.origin_pos[0]
		self.origin_boundary = [self.origin_pos, P.origin_size // 2]
		self.add_boundary("origin", self.origin_boundary, CIRCLE_BOUNDARY)
		self.rc.draw_listener.add_boundaries([
			('start', self.origin_boundary, CIRCLE_BOUNDARY),
			('stop', self.origin_boundary, CIRCLE_BOUNDARY)
		])

		# If using log file, write out the intertrial interval info to it (is this still useful?)
		self.log("\n\n********** TRIAL {0} ***********\n".format(P.trial_number))
		if self.intertrial_start:
			self.intertrial_end = time.time()
			intertrial_interval = self.intertrial_end - self.intertrial_start
			self.log(str(intertrial_interval) + "\n")
		if P.trial_number > 1:
			self.log("t{0}_intertrial_interval_end".format(P.trial_number - 1), True)
			self.log("write_out")
		self.log("t{0}_intertrial_interval_start".format(P.trial_number), True)
		self.intertrial_start = time.time()

		# Let participant self-initiate next trial
		self.start_trial_button()


	def trial(self):

		start_delay = CountDown(P.origin_wait_time)
		while start_delay.counting():
			ui_request()
			fill()
			blit(self.tracker_dot, 5, self.origin_pos)
			flip()

		animate_start = self.evm.trial_time
		self.figure.animate()
		animate_time = self.evm.trial_time - animate_start
		avg_velocity = self.figure.path_length / animate_time

		if self.response_type == PHYS:
			self.physical_trial()
		elif self.response_type == MOTR:
			self.imagery_trial()
		else:
			self.control_trial()

		fill()
		flip()

		if self.__practicing__:
			return

		return {
			"session_num": self.session_number,
			"block_num": P.block_number,
			"trial_num": P.trial_number,
			"response_type": self.response_type,
			"feedback_type": self.feedback_type,
			"figure_type": self.figure_name,
			"figure_file": self.file_name + ".tlf",
			"stimulus_gt": self.animate_time, # intended animation time
			"stimulus_mt": animate_time, # actual animation time
			"avg_velocity": avg_velocity, # in pixels per second
			"path_length": self.figure.path_length,
			"trace_file": (self.file_name + ".tlt") if self.response_type == PHYS else 'NA',
			"rt": self.rt,
			"it": self.it,
			"control_question": self.control_question if self.response_type == CTRL else 'NA',
			"control_response": self.control_response,
			"mt": self.mt
		}


	def trial_clean_up(self):

		if not self.__practicing__:
			self.figure.write_out(self.file_name + ".tlf")
			self.figure.write_out(self.file_name + ".tlt", self.drawing)
		self.rc.draw_listener.reset()
		self.control_bar.reset()


	def clean_up(self):

		if self.session_number == self.session_count and P.enable_learned_figures_querying:
			self.fig_dir = os.path.join(self.p_dir, "learned")
			if not os.path.exists(self.fig_dir):
				os.makedirs(self.fig_dir)

			learned_fig_num = 1
			if query(user_queries.experimental[3]) == "y":
				self.origin_pos = (P.screen_c[0], int(P.screen_y * 0.8))
				self.origin_boundary = [self.origin_pos, P.origin_size // 2]
				while True:
					self.setup_response_collector()
					self.rc.draw_listener.add_boundaries([
						('start', self.origin_boundary, CIRCLE_BOUNDARY),
						('stop', self.origin_boundary, CIRCLE_BOUNDARY)
					])
					self.start_trial_button()
					self.capture_learned_figure(learned_fig_num)
					if query(user_queries.experimental[4]) == "y":
						learned_fig_num += 1
					else:
						break

		# if the entire experiment is successfully completed, update the sessions_completed column
		q_str = "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?"
		self.db.query(q_str, QUERY_UPD, q_vars=[self.session_number, P.participant_id])

		# log session data to database
		session_data = {
			'participant_id': P.participant_id,
			'user_id': self.user_id,
			'session_number': self.session_number,
			'completed': now(True)
		}
		self.db.insert(session_data, "sessions")

		# show 'experiment complete' message before exiting experiment
		msg = message(P.experiment_complete_message, "instructions", blit_txt=False)
		flush()
		fill()
		blit(msg, registration=5, location=P.screen_c)
		flip()
		any_key()



	### Assorted helper methods called within the main experiment structure ###

	def start_trial_button(self):

		fill()
		blit(self.next_trial_box, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		blit(self.next_trial_msg, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		flip()

		if P.demo_mode or P.dm_always_show_cursor:
			show_mouse_cursor()

		flush()
		clicked = False
		while not clicked:
			event_queue = pump(True)
			for e in event_queue:
				if e.type == SDL_MOUSEBUTTONDOWN:
					clicked = self.within_boundary("next trial button", [e.button.x, e.button.y])
				elif e.type == SDL_KEYDOWN:
					ui_request(e.key.keysym)

		if not (P.demo_mode or P.dm_always_show_cursor):
			hide_mouse_cursor()


	def display_refresh(self):

		fill()
		origin = self.origin_active if self.rc.draw_listener.active else self.origin_inactive
		blit(origin, 5, self.origin_pos, flip_x=P.flip_x)
		if P.dm_render_progress or self.feedback_type in (FB_ALL, FB_DRAW):
			try:
				drawing = self.rc.draw_listener.render_progress()
				blit(drawing, 5, P.screen_c, flip_x=P.flip_x)
			except TypeError:
				pass
		flip()


	def imagery_trial(self):

		fill()
		blit(self.origin_inactive, 5, self.origin_pos, flip_x=P.flip_x)
		flip()

		start = self.evm.trial_time
		if P.demo_mode or P.dm_always_show_cursor:
			show_mouse_cursor()

		at_origin = False
		while not at_origin:
			x, y, button = mouse_pos(return_button_state=True)
			left_button_down = button == 1
			if self.within_boundary('origin', (x, y)) and left_button_down:
				at_origin = True
				self.rt = self.evm.trial_time - start
			ui_request()
		fill()
		blit(self.origin_active, 5, self.origin_pos, flip_x=P.flip_x)
		flip()

		while at_origin:
			x, y, button = mouse_pos(return_button_state=True)
			left_button_down = button == 1
			if not (self.within_boundary('origin', (x, y)) and left_button_down):
				at_origin = False
		self.mt = self.evm.trial_time - (self.rt + start)
		if P.demo_mode:
			hide_mouse_cursor()


	def physical_trial(self):

		self.rc.collect()
		self.rt = self.rc.draw_listener.start_time
		self.drawing = self.rc.draw_listener.responses[0][0]
		self.it = self.rc.draw_listener.first_sample_time - self.rt
		self.mt = self.rc.draw_listener.responses[0][1]

		if self.feedback_type in (FB_ALL, FB_RES) and not self.__practicing__:
			flush()
			fill()
			blit(self.figure.render(trace=self.drawing), 5, P.screen_c, flip_x=P.flip_x)
			flip()
			start = time.time()
			while time.time() - start < P.feedback_duration / 1000.0:
				ui_request()


	def control_trial(self):

		if P.dm_always_show_cursor:
			show_mouse_cursor()

		self.control_bar.update_message(P.control_q.format(self.control_question))
		self.control_bar.render()
		self.control_bar.collect_response()

		self.rt = self.control_bar.rt
		self.mt = self.control_bar.mt
		self.control_response = self.control_bar.response


	def _generate_figure(self, duration):

		failures = 0
		figure = None
		gen_start = time.time()
		while not figure:
			ui_request()
			try:
				figure = TraceLabFigure(animate_time = duration, handedness = self.handedness)
				figure.render()
				figure.prepare_animation()
			except RuntimeError as e:
				print(e)
				failures += 1
				if failures > 10:
					print("\nUnable to generate a viable figure after 10 tries, quitting...\n")
					self.quit()

		# Print warning if load time was particularly slow for a given figure
		if (time.time() - gen_start) > 0.5:
			cso("<red>Warning: figure generation took unexpectedly long. "
				"({0} seconds)</red>".format(round(time.time() - gen_start, 2)))

		return figure


	def capture_figures(self):

		txt = ("Welcome to the TraceLab figure generator!\n\n"
			  "Generated figures will be saved to 'ExpAssets/Resources/figures/'. {0}\n\n"
			  "Press any key to begin.")
		auto_txt = "TraceLab will automatically exit when figure generation is complete."
		txt = txt.format(auto_txt if P.auto_generate else "")

		fill()
		message(txt, "default", registration=5, location=P.screen_c, align='center', blit_txt=True)
		flip()
		any_key()

		if P.development_mode:
			print("Random seed: {0}".format(P.random_seed))

		if P.auto_generate:

			num_figs = P.auto_generate_count
			for i in range(0, num_figs):

				txt = "Generating figure {0} of {1}...".format(i + 1, num_figs)
				msg = message(txt, "default", blit_txt=False)
				fill()
				blit(msg, 5, P.screen_c)
				flip()

				figure = self._generate_figure(duration=5000.0)
				figure.write_out("figure{0}_{1}.tlf".format(i + 1, P.random_seed))

		else:

			done = False
			while not done:

				msg = message("Generating...", "default", blit_txt=False)
				fill()
				blit(msg, 5, P.screen_c)
				flip()

				figure = self._generate_figure(duration=5000.0)
				while True:

					# Animate figure on screen with dot, then show full rendered shape
					figure.animate()
					animation_dur = round(figure.trial_a_frames[-1][2] * 1000, 2)
					msg = message("Press any key to continue.", blit_txt=False)
					msg_time = message("Duration: {0} ms".format(animation_dur), blit_txt=False)
					fill()
					figure.draw()
					blit(msg, 3, (P.screen_x - 30, P.screen_y - 25))
					blit(msg_time, 7, (30, 25))
					flip()
					any_key()

					# Prompt participants whether they want to (q)uit, (r)eplay animation,
					# (d)iscard figure and move to next, or (s)ave figure to file
					resp = query(user_queries.experimental[6])
					if resp == "r": # replay
						continue
					elif resp == "d": # discard
						break
					elif resp == "q": # quit
						done = True
						break
					elif resp == "s": # save
						f_name = query(user_queries.experimental[7]) + ".tlf"
						msg = message("Saving... ", blit_txt=False)
						fill()
						blit(msg, 5, P.screen_c)
						flip()
						figure.write_out(f_name)
						break


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

		if self.log_f:
			if msg != "write_out":
				if t:
					self.intertrial_timing_logs[msg] = time.time()
				else:
					self.log_f.write(msg)
			else:
				key = 't{0}_intertrial_interval_{1}'
				iti_index = P.trial_number - 1
				iti_start = self.intertrial_timing_logs[key.format(iti_index, "start")]
				iti_end = self.intertrial_timing_logs[key.format(iti_index, "end")]
				iti = str(iti_end - iti_start)
				self.log_f.write(utf8("intertrial_interval:".ljust(32, " ") + iti + "\n"))


	def quit(self):
		# Properly close trigger port for hardware that needs it
		if self.trigger is not None:
			self.trigger.close()
		try:
			self.log_f.close()
		except AttributeError:
			pass
		super(TraceLab, self).quit()


	@property
	def file_name(self):
		file_name_data = [
			P.participant_id, P.block_number, P.trial_number,
			now(True, "%Y-%m-%d"), self.session_number
		]
		return "p{0}_s{4}_b{1}_t{2}_{3}".format(*file_name_data)
