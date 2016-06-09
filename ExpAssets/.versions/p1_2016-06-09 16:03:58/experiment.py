# "fixate" at draw start; show image (maintain "fixation"; draw after SOA

import klibs

__author__ = "Jonathan Mulle"

import imp
from klibs.KLDraw import *
from klibs.KLUtilities import *
from klibs.KLConstants import *
from klibs.KLEventInterface import EventTicket as ET
from klibs.KLExceptions import TrialException
#df = imp.load_source('TraceLabObjects.DrawFigure', 'ExpAssets/Resources/code/TraceLabObjects')
#sld = imp.load_source('TraceLabObjects.Slider', 'ExpAssets/Resources/code/TraceLabObjects')
tlo = imp.load_source('TraceLabObjects', 'ExpAssets/Resources/code/TraceLabObjects')

from klibs import BoundaryInspector
import os

from hashlib import sha1

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255,0,0,255)
GREEN = (0,255,0,255)
BOT_L = 0
TOP_L = 1
TOP_R = 2

# jon hates retyping strings
PHYSICAL_MODE = "p"
IMAGERY_MODE = "i"
CONTROL_MODE = "c"

class TraceLab(klibs.Experiment, BoundaryInspector):
	# session vars
	p_dir = None
	fig_dir = None
	# graphical elements
	value_slider = None
	canvas = None
	canvas_size = 800  #px
	canvas_color = WHITE
	canvas_border = BLACK
	origin_proto = None
	origin_active = None
	origin_inactive = None
	origin_active_color = GREEN
	origin_inactive_color = RED
	origin_size = 20
	origin_pos = None
	origin_boundary = None
	tracker_dot_proto = None
	tracker_dot_size = 3
	tracker_dot = None

	instructions_1 = None
	instructions_2 = None
	loading_msg = None
	control_fail_msg = None
	response_window_extension = 1 # second
	response_window = None  # speed + constant

	# debug & configuration
	show_drawing = True
	sample_exposure_time = 4500

	# dynamic trial vars
	boundaries = {}
	use_random_figures = False
	drawing = []
	rt = None
	mode = None
	seg_estimate = None
	figure = None
	figure_dots = None
	figure_segments = None
	vertices_reported = None



	def __init__(self, *args, **kwargs):
		super(TraceLab, self).__init__(*args, **kwargs)


	def setup(self):
		try:
			if Params.session_number == 1 :
				self.p_dir = os.path.join(Params.data_path, "p{0}_{1}".format(Params.user_data[0], Params.user_data[-2]))
				self.fig_dir = os.path.join(self.p_dir, "random_figures")
				if not os.path.exists(self.p_dir):
					os.mkdir(self.p_dir)
				if not os.path.exists(self.fig_dir):
					os.mkdir(self.fig_dir)
		except AttributeError:
			pass
		self.origin_proto = Ellipse(self.origin_size)
		self.tracker_dot_proto = Ellipse(self.tracker_dot_size)
		self.tracker_dot_proto.fill = [255, 0, 0]
		self.tracker_dot = self.tracker_dot_proto.render()
		self.text_manager.add_style('instructions', 32, [255, 255, 255, 255])
		self.text_manager.add_style('error', 32, [255, 0, 0, 255])
		self.text_manager.add_style('tiny', 12, [255, 255,255, 255])
		self.text_manager.add_style('small', 16, [255, 255,255, 255])

		if Params.capture_figures_mode:
			self.capture_figures()
		self.value_slider = tlo.Slider(self, 950, 800, 15, 20, (75,75,75), RED)
		self.use_random_figures = Params.session_number not in (1, 5)
		self.origin_proto.fill = self.origin_active_color
		self.origin_active = self.origin_proto.render()
		self.origin_proto.fill = self.origin_inactive_color
		self.origin_inactive = self.origin_proto.render()
		self.origin_pos = (Params.screen_c[0], Params.screen_c[1] + self.canvas_size // 2)
		self.add_boundary("origin", [self.origin_pos, self.origin_size // 2], CIRCLE_BOUNDARY)
		half_or = self.origin_size // 2
		ob_x1 = self.origin_pos[0] - half_or
		ob_y1 = self.origin_pos[1] - half_or
		ob_x2 = self.origin_pos[0] + half_or
		ob_y2 = self.origin_pos[0] + half_or
		self.origin_boundary = [(ob_x1, ob_y1), (ob_x2, ob_y2)]
		self.instructions_1 = "On each trial you will have {0} seconds to study a random figure.\nYou will later be asked to draw it.\nPress any key to begin.".format(self.sample_exposure_time // 1000)
		self.instructions_2 = "Now draw the figure you have just seen.\n - Start by placing the cursor on the red dot. \n - End by placing the cursor on the green dot. \n\nPress any key to proceed."
		self.loading_msg = self.message("Generating figure, just one moment...", "default", blit=False)
		self.control_fail_msg = self.message("Please keep your finger on the start area for the complete duration.", 'error', blit=False )

	def block(self):
		self.fill()
		self.message(self.instructions_1, 'instructions', registration=5, location=Params.screen_c)
		self.flip()
		self.any_key()

	def setup_response_collector(self):

		self.rc.uses(RC_DRAW)
		cb_xy1 = Params.screen_c[0] - self.canvas_size // 2
		cb_xy2 = Params.screen_c[0] + self.canvas_size // 2
		self.rc.end_collection_event = 'response_period_end'
		self.rc.draw_listener.add_boundaries([('start', self.origin_boundary, CIRCLE_BOUNDARY),
											  ('stop', self.origin_boundary, CIRCLE_BOUNDARY),
											  ('canvas', [(cb_xy1, cb_xy1), (cb_xy2, cb_xy2)], RECT_BOUNDARY)])
		self.rc.draw_listener.canvas_size = Params.screen_x_y
		self.rc.draw_listener.start_boundary = 'start'
		self.rc.draw_listener.stop_boundary = 'stop'
		self.rc.draw_listener.canvas_boundary = 'canvas'
		self.rc.draw_listener.show_active_cursor = False
		self.rc.draw_listener.show_inactive_cursor = True
		self.rc.draw_listener.x_offset = Params.screen_c[0] - self.canvas_size // 2
		self.rc.draw_listener.y_offset = Params.screen_c[1] - self.canvas_size // 2
		self.rc.draw_listener.origin = self.origin_pos
		self.rc.draw_listener.interrupts = True
		self.rc.display_callback = self.display_refresh
		self.rc.display_callback_args = [True]

	def trial_prep(self):
		self.drawing = NA
		self.seg_estimate = -1
		self.fill()
		self.blit(self.loading_msg, 5, Params.screen_c)
		self.flip()

		self.figure = df(self)
		self.value_slider.update_range(self.figure.seg_count)

	def trial(self):
		# while self.evi.before('end_exposure', True):
		self.figure.animate(self.speed)
		if Params.exp_condition == IMAGERY_MODE:
			self.motor_imagery_trial()
		if Params.exp_condition == PHYSICAL_MODE:
			self.physical_trial()
		if Params.exp_condition == CONTROL_MODE:
			self.control_trial()
		self.fill()
		self.message("Press any key to begin the next trial.", 'instructions', registration=5, location=Params.screen_c, flip=True)
		self.any_key()

		return {
			"block_num": Params.block_number,
			"trial_num": Params.trial_number,
			"figure": self.figure.frames,
			"drawing": self.drawing_name,
			"seg_estimate": self.seg_estimate,
			"rt": self.rt,
		}

	def trial_clean_up(self):
		self.value_slider.reset()
		self.figure.write_out(self.fig_dir, self.figure.file_name)
		if Params.exp_condition == PHYSICAL_MODE:
			pass
			# draw_file =

	def clean_up(self):
		# if the entire experiment is successfully completed, update the sessions_completed column
		q_str = "UPDATE `participants` SET `sessions_completed` = ? WHERE `id` = ?"
		self.database.query(q_str, qvars = [Params.session_number, Params.participant_id])

	def display_refresh(self, flip=True):
		self.fill()
		self.blit(self.canvas, 5, Params.screen_c)
		origin = self.origin_active  if self.rc.draw_listener.active else self.origin_inactive
		self.blit(origin, 5, self.origin_pos)
		if self.show_drawing:
			try:
				drawing = self.rc.draw_listener.render_progress()
				self.blit(drawing, 5, Params.screen_c)
			except TypeError:
				pass
		if flip:
			self.flip()

	def set_session(self, id_str=None):
		session_data_str = "SELECT * FROM `sessions` WHERE `participant_id` = ?"
		if id_str:
			userhash = sha1(id_str).hexdigest()
			user_data_str = "SELECT * FROM `participants` WHERE `userhash` = ?"
			user_data = self.database.query(user_data_str, q_vars=[userhash]).fetchall()[0]
			Params.participant_id = user_data[0]
			Params.random_seed = str(user_data[2])
			session_data = self.database.query(session_data_str, q_vars=[Params.participant_id]).fetchall()[0]
			Params.session_id = session_data[0]
			Params.exp_condition = session_data[2]
			Params.session_number = session_data[3] + 1
		else:
			Params.session_number = 1
			q_str = "SELECT * FROM `participants` WHERE `id` = ?"
			user_data = self.database.query(q_str, q_vars=[Params.participant_id]).fetchall()[0]
		Params.user_data = user_data

		if Params.session_number == 1:
			try:
				 session_data = self.database.query(session_data_str, q_vars=[Params.participant_id]).fetchall()[0]
				 Params.exp_condition = session_data[2]
			except IndexError:
				Params.exp_condition = self.query("Please enter an experimental condition identifier:", accepted=('p', 'm', 'c'))
				self.database.init_entry('sessions')
				self.database.log('participant_id', Params.participant_id)
				self.database.log('sessions_completed', 0)
				self.database.log('exp_condition', Params.exp_condition)
				Params.session_id = self.database.insert()
		Params.demographics_collected = True

	def control_trial(self):
		self.fill()
		self.blit(self.origin_inactive)
		self.flip()
		while not self.within_boundary('origin', mouse_pos()):
			self.ui_request()
		Params.clock.register_events([ET('end_exposure', self.speed)])
		while self.evi.before('end_exposure', True):
			if not self.within_boundary('origin', mouse_pos()):
				self.fill()
				self.blit(self.control_fail_msg, 5, Params.screen_c)
				self.flip()
				self.any_key()
				raise TrialException()

	def physical_trial(self):
		self.fill()
		self.message(self.instructions_2, 'instructions', registration=5, location=Params.screen_c, flip=True)
		self.any_key()
		self.fill()
		self.rc.collect()
		self.drawing = self.rc.draw_listener.responses[0][0]
		self.rt = self.rc.draw_listener.responses[0][1]

	def motor_imagery_trial(self):
		self.rt = -1
		self.drawing = NA
		while not self.vertices_reported:
			self.seg_estimate = self.value_slider.slide()
		cont = self.query("You reported {0} segments. Is that correct? \n(y)es or (n)o", accepted=['y', 'n', 'Y','N'])

		return self.motor_imagery_trial() if cont in ['n', 'N'] else None

	def show_figure(self):
		surf = aggdraw.Draw("RGBA", (800, 800), (255, 255, 255, 255))
		p_str = "M{0} {1}".format(*self.figure_segments[0])
		for s in chunk(self.figure_segments, 2):
			try:
				p_str += " L{0} {1} {2} {3}".format(*(list(s[0]) + list(s[1])) )
			except IndexError:
				pass
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0, 0), sym, aggdraw.Pen((255, 0, 0), 1, 255))
		surf = aggdraw_to_array(surf)

		f_count = len(self.figure_segments)
		self.fill()
		draw_in = float(self.animate_time)
		min_rate = 0.015
		max_frames = int(draw_in / min_rate)
		rate =  draw_in / len(self.figure_segments)
		skip_frame = int(f_count / max_frames)
		removed = 0
		while len(self.figure_segments) > max_frames:
			removed += 1
			try:
				self.figure_segments.remove(self.figure_segments[removed * skip_frame])
			except IndexError:
				break

		last_f = time.time()
		frame_start = time.time()
		f = 0
		while time.time() - frame_start < draw_in:
			pump()
			if time.time() > rate + last_f:
				last_f = time.time()
				f += 1
			pos = self.figure_segments[f]
			self.fill()
			self.blit(self.canvas, 5, Params.screen_c)
			self.blit(surf, 5, Params.screen_c)
			self.blit(self.tracker_dot, 5, pos)
			self.flip()

	def capture_figures(self):
		self.fill()
		self.message("Press command+q at any time to exit.\nPress any key to continue.", "default", registration=5, location=Params.screen_c, flip=True)
		self.any_key()
		finished = False
		while not finished:
			finished = self.__review_figure()
		self.quit()

	def __review_figure(self):
		self.fill()
		if not self.figure:
			self.figure = df(self)
		# self.figure.draw(dots=True, flip=False)
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
			f_name = "figure_" + str(now(True)) + ".tlf"
			path = os.path.join(Params.resource_dir, "figures")
			self.figure.write_out(path, f_name, False)


	@property
	def drawing_name(self):
		fname_data = [Params.participant_id, Params.block_number, Params.trial_number, now(True, "%Y-%m-%d")]
		return "p{0}_b{1}_t{2}_{3}.tld".format(*fname_data)









