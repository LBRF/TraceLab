# -*- coding: utf-8 -*-
__author__ = "Jonathan Mulle"

import os
import time
import sdl2

from random import choice

import klibs
from klibs import P
from klibs.KLConstants import STROKE_OUTER
from klibs.KLBoundary import BoundaryInspector, RectangleBoundary, CircleBoundary
from klibs.KLTime import CountDown, precise_time
from klibs.KLUserInterface import any_key, ui_request, show_cursor, hide_cursor, mouse_clicked
from klibs.KLUtilities import pump, flush, scale, now, utf8
from klibs.KLUtilities import colored_stdout as cso
from klibs.KLGraphics import blit, fill, flip
from klibs.KLGraphics.KLDraw import Ellipse, Rectangle
from klibs.KLText import add_text_style
from klibs.KLCommunication import user_queries, message, query

from TraceLabSession import TraceLabSession
from TraceLabFigure import TraceLabFigure, save_figure, save_template
from utils import draw_borders, touchscreen_detected, get_touch_coords, get_hostname
from ButtonBar import ButtonBar
from responselisteners import DrawingListener, DrawSurface
from instructions import play_tutorial


WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
TRACE_COLOUR = (255, 80, 125, 255)

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
	figure_set_name = "NA"

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


	def __init__(self):

		klibs.Experiment.__init__(self)
		BoundaryInspector.__init__(self)
		P.flip_x = P.mirror_mode


	def __practice__(self):

		self.figure_name = P.practice_figure
		self.animate_time = P.practice_animation_time

		self.__practicing__ = True
		self.trial_prep()
		self.trial()
		self.trial_clean_up()
		self.__practicing__ = False


	def setup(self):

		# Set up custom text styles for the experiment
		add_text_style('instructions', 18, color=WHITE)
		add_text_style('error', 18, color=RED)
		add_text_style('tiny', 12, color=WHITE)
		add_text_style('small', 14, color=WHITE)

		# Pre-render shape stimuli
		dot_stroke = [P.dot_stroke, P.dot_stroke_col, STROKE_OUTER] if P.dot_stroke > 0 else None
		self.tracker_dot = Ellipse(P.dot_size, stroke=dot_stroke, fill=P.dot_color).render()
		self.origin_active = Ellipse(P.origin_size, fill=self.origin_active_color).render()
		self.origin_inactive = Ellipse(P.origin_size, fill=self.origin_inactive_color).render()

		# If capture figures mode, generate, view, and optionally save some figures
		if P.capture_figures_mode:
			self.capture_figures()
			self.quit()

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

		# Initialize participant ID and session options, reloading ID if it already exists
		self.session = TraceLabSession()
		self.user_id = self.session.user_id
		self.filename_id = str(P.participant_id)
		if P.append_hostname:
			self.filename_id += "-{0}".format(get_hostname())


		# Add flags for first block/trial of run, needed for resuming mid-session
		self.first_block = True
		self.first_trial = True

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
		self.control_bar = ButtonBar(
			buttons = ["1", "2", "3", "4", "5"],
			button_size = P.btn_size, screen_margins = P.btn_s_pad, y_offset = P.y_pad,
			message_txt = P.control_q
		)

		# Initialize the drawing response listener
		self.draw_listener = DrawingListener(loop_callback=self.display_refresh)

		# Initialize 'next trial' button
		button_x = 250 if self.handedness == LEFT_HANDED else P.screen_x - 250
		button_y = P.screen_y - 100
		button_w, button_h = (300, 75)
		xy1 = (button_x - button_w // 2, button_y - button_h // 2)
		xy2 = (button_x + button_w // 2, button_y + button_h // 2)
		self.next_trial_msg = message(P.next_trial_message, 'default')
		self.next_trial_box = Rectangle(button_w, button_h, stroke=(2, WHITE, STROKE_OUTER))
		self.next_trial_button_loc = (button_x, button_y)
		self.next_trial_bounds = RectangleBoundary("next trial", xy1, xy2)


		# Initialize instructions and practice button bar for each condition
		block_msg_tmp = "Remember to {0}!\n\nTap the screen to begin."
		self.block_messages = {
			PHYS: block_msg_tmp.format("match the speed"),
			MOTR: block_msg_tmp.format("match the speed"),
			CTRL: block_msg_tmp.format("take your time"),
		}
		self.practice_instructions = message(
			P.practice_instructions, "instructions",
			align="center", blit_txt=False
		)
		self.practice_button_bar = ButtonBar(
			["Replay", "Practice", "Begin"],
			[200, 100], P.btn_s_pad, P.y_pad, finish_button=False
		)

		# Determine whether cursor should be shown or hidden
		touchscreen = touchscreen_detected()
		if P.force_show_cursor or (P.development_mode and not touchscreen):
			show_cursor()
		else:
			hide_cursor()

		# Import all pre-generated figures needed for the current session
		figures = list(set(self.trial_factory.exp_factors["figure_name"]))
		figures.append(P.practice_figure)
		for f in figures:
			if f != "random":
				ui_request()
				fig_path = os.path.join(P.resources_dir, "figures", f)
				self.test_figures[f] = TraceLabFigure(fig_path, handedness = self.handedness)


	def block(self):

		# If reloading incomplete session, update block number accordingly
		if self.first_block:
			blocks_in_session = len(self.blocks)
			P.block_number = (P.blocks_per_experiment - blocks_in_session) + 1
			self.first_block = False

		# Get response type and feedback type for block
		self.response_type = self.block_factors[P.block_number - 1]['response_type']
		self.feedback_type = self.block_factors[P.block_number - 1]['feedback_type']

		# If on first block of session, or response type is different from response type of
		# previous block, do tutorial animation and practice
		if self.response_type != self.prev_response_type:

			# Play tutorial for current response type & enter practice
			if P.enable_practice:
				if P.block_number == 1:
					fill()
					blit(self.practice_instructions, 5, P.screen_c)
					flip()
					any_key()
				else:
					self.start_trial_button()
				play_tutorial(self, self.response_type)
				self.practice_menu()

			self.prev_response_type = self.response_type

		block_msg_txt = self.block_messages[self.response_type]
		block_msg = message(block_msg_txt, "instructions", align="center")
		for i in range(1,4):
			# we do this a few times to avoid block messages being skipped due to duplicate input
			# from the touch screen we use
			ui_request()
			fill()
			blit(block_msg, 5, P.screen_c, flip_x=P.flip_x)
			draw_borders(P.border_size, WHITE)
			flip()
		any_key()


	def trial_prep(self):

		# If reloading incomplete block, update trial number accordingly
		if self.first_trial:
			trials_in_block = len(self.blocks[0])
			P.trial_number = (P.trials_per_block - trials_in_block) + 1
			self.first_trial = False

		# Initialize/reset trial variables before beginning trial
		self.control_question = choice(["LEFT", "RIGHT", "UP", "DOWN"])
		self.rt = 0.0
		self.it = 0.0
		self.animate_time = int(self.animate_time)
		self.control_response = -1
		self.figure = None
		self.drawing = None
		self.a_frames = [] # figure animation frames
		self.live_feedback = None

		# Either load a pre-generated figure or generate a new one, depending on trial
		if self.figure_name == "random":
			self.figure = self._generate_figure(duration=self.animate_time)
		else:
			self.figure = self.test_figures[self.figure_name]
			self.figure.prepare_animation(self.animate_time)
		self.figure.render()

		# Initialize origin position and origin boundaries based on the loaded figure
		self.origin_pos = list(self.figure.points[0])
		origin_bounds = CircleBoundary('origin', self.origin_pos, P.origin_size // 2)
		self.add_boundary(origin_bounds)
		self.draw_listener.set_origin(origin_bounds)

		# Let participant self-initiate next trial
		self.start_trial_button()


	def trial(self):

		start_delay = CountDown(P.origin_wait_time)
		while start_delay.counting():
			ui_request()
			fill()
			if P.show_figure_at_onset:
				blit(self.figure.rendered, 5, P.screen_c)
			blit(self.tracker_dot, 5, self.origin_pos)
			draw_borders(P.border_size, WHITE)
			flip()

		animate_start = time.perf_counter()
		self.a_frames = self.animate_figure(self.figure)
		animate_time = time.perf_counter() - animate_start
		avg_velocity = self.figure.path_length / animate_time

		if self.response_type == PHYS:
			self.physical_trial()
		elif self.response_type == MOTR:
			self.imagery_trial()
		else:
			self.control_trial()

		if self.feedback_type in (FB_ALL, FB_RES) and not self.__practicing__:
			flush()
			fill()
			blit(self.figure.render(trace=self.drawing), 5, P.screen_c)
			draw_borders(P.border_size, WHITE)
			flip()
			start = time.time()
			while time.time() - start < P.feedback_duration / 1000.0:
				ui_request()

		fill()
		draw_borders(P.border_size, WHITE)
		flip()

		if self.__practicing__:
			return

		return {
			"session_num": P.session_number,
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
			outpath = os.path.join(self.fig_dir, self.file_name + ".zip")
			save_figure(outpath, self.figure, self.a_frames, self.drawing)


	def clean_up(self):

		if P.session_number == self.session_count and P.enable_learned_figures_querying:
			self.fig_dir = os.path.join(self.p_dir, "learned")
			if not os.path.exists(self.fig_dir):
				os.makedirs(self.fig_dir)

			learned_fig_num = 1
			if query(user_queries.experimental[3]) == "y":
				self.origin_pos = (P.screen_c[0], int(P.screen_y * 0.8))
				origin = CircleBoundary('origin', self.origin_pos, P.origin_size // 2)
				self.draw_listener.set_origin(origin)
				while True:
					self.start_trial_button()
					self.capture_learned_figure(learned_fig_num)
					if query(user_queries.experimental[4]) == "y":
						learned_fig_num += 1
					else:
						break

		# if the entire experiment is successfully completed, update the sessions_completed column
		self.db.update('participants', {'sessions_completed': P.session_number})

		# log session data to database
		session_data = {
			'participant_id': P.participant_id,
			'user_id': self.user_id,
			'session_number': P.session_number,
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
		draw_borders(P.border_size, WHITE)
		blit(self.next_trial_box, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		blit(self.next_trial_msg, 5, self.next_trial_button_loc, flip_x=P.flip_x)
		flip()

		flush()
		clicked = False
		while not clicked:
			clicked = mouse_clicked(within=self.next_trial_bounds)


	def animate_figure(self, figure, show_figure=False, borders=True):

		start = None
		frames = []
		for f in figure.a_frames:

			ui_request()
			fill()
			if show_figure:
				blit(figure.rendered, 5, P.screen_c)
			blit(self.tracker_dot, 5, f)
			if borders:
				draw_borders(P.border_size, WHITE)
			flip()

			if start is None:
				timestamp = 0.0
				start = precise_time()
			else:
				timestamp = round(precise_time() - start, 7)
			frames.append((f[0], f[1], timestamp))

		return frames


	def display_refresh(self):

		fill()
		draw_borders(P.border_size, WHITE)
		origin = self.origin_active if self.draw_listener.started else self.origin_inactive
		blit(origin, 5, self.origin_pos, flip_x=P.flip_x)
		if P.dm_render_progress or self.feedback_type in (FB_ALL, FB_DRAW):
			if not self.live_feedback:
				self.live_feedback = DrawSurface(P.screen_x_y, TRACE_COLOUR, 1)
			self.live_feedback.update(self.draw_listener.points)
			drawing = self.live_feedback.render()
			blit(drawing, 7, (0, 0))
		flip()


	def imagery_trial(self):

		fill()
		draw_borders(P.border_size, WHITE)
		blit(self.origin_inactive, 5, self.origin_pos, flip_x=P.flip_x)
		flip()

		start = time.perf_counter()
		at_origin = False
		while not at_origin:
			loc = get_touch_coords()
			if loc and self.within_boundary('origin', loc):
				at_origin = True
				self.rt = time.perf_counter() - start
			ui_request()
		fill()
		draw_borders(P.border_size, WHITE)
		blit(self.origin_active, 5, self.origin_pos, flip_x=P.flip_x)
		flip()

		while at_origin:
			# Wait until finger lifted to end response
			loc = get_touch_coords()
			if not loc:
				at_origin = False
		self.mt = time.perf_counter() - (self.rt + start)


	def physical_trial(self):

		self.display_refresh()
		resp = self.draw_listener.collect()
		self.drawing, self.rt, self.it, self.mt = resp


	def control_trial(self):

		control_q_txt = P.control_q.format(self.control_question)
		self.control_bar.update_message(control_q_txt)

		resp, rt_first, rt_final, mt = self.control_bar.collect()

		self.rt = rt_final
		self.mt = mt
		self.control_response = resp


	def _generate_figure(self, duration):

		failures = 0
		figure = None
		gen_start = time.time()
		while not figure:
			ui_request()
			try:
				figure = TraceLabFigure(handedness = self.handedness)
				figure.render()
				figure.prepare_animation(duration)
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

		template_dir = os.path.join(P.resources_dir, "figures")
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
				figname = "figure{0}_{1}".format(i + 1, P.random_seed)
				outpath = os.path.join(template_dir, figname)
				save_template(outpath, figure)

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
					frames = self.animate_figure(figure, borders=False)
					animation_dur = round(frames[-1][2] * 1000, 2)
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
						figname = query(user_queries.experimental[7])
						outpath = os.path.join(template_dir, figname)
						msg = message("Saving... ", blit_txt=False)
						fill()
						blit(msg, 5, P.screen_c)
						flip()
						save_template(outpath, figure)
						break


	def capture_learned_figure(self, fig_number):

		outfile = "p{0}_learned_figure_{1}.zip".format(self.filename_id, fig_number)
		outpath = os.path.join(self.fig_dir, outfile)
		self.live_feedback = None
		self.display_refresh()
		learned = self.draw_listener.collect()[0]
		save_figure(outpath, tracing=learned)


	def practice_menu(self):

		choice = None
		while choice != "Begin":
			choice, rt = self.practice_button_bar.collect()
			if choice == "Replay":
				play_tutorial(self, self.response_type)
			elif choice == "Practice":
				self.__practice__()


	def quit(self):
		# Properly close trigger port for hardware that needs it
		if self.trigger is not None:
			self.trigger.close()
		super(TraceLab, self).quit()


	@property
	def file_name(self):
		file_name_data = [
			self.filename_id, P.block_number, P.trial_number,
			now(True, "%Y-%m-%d"), P.session_number
		]
		return "p{0}_s{4}_b{1}_t{2}_{3}".format(*file_name_data)
