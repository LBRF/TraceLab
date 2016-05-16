# "fixate" at draw start; show image (maintain "fixation"; draw after SOA

import klibs

__author__ = "Jonathan Mulle"
import aggdraw
import time
from random import choice, randrange
import numpy as np
from PIL import ImagePath, ImageDraw, Image
from klibs import Params as Params
from klibs.KLDraw import *
from klibs.KLKeyMap import KeyMap
from klibs.KLUtilities import *
from klibs.KLConstants import *
from klibs.KLEventInterface import EventTicket as ET
from itertools import chain


WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255,0,0,255)
GREEN = (0,255,0,255)
BOT_L = 0
TOP_L = 1
TOP_R = 2

"""
 Everything involved in the bezier function is patched together from various stack overflow investigations. The linear
 one is my own.

 I'm using these to create an animation of a dot following through a path of connected linear and bezier segments; the
 full script creates a big list of segments where each end point is the beginning of the next segment's start point.
 The problem, isn't that this don't work; it does, and quite well, really. The problem is that I have:

 a) made no effort to control the resolution of the output, so I have a very different delta d, per point, between large
 curves vs small curves, and either vs lines. The amounts to an extremely variously paced animation if each point is
 treated as a frame.

 b) don't really know *how* to control said resolution—especially in the bezier condition, where the path is closer to
 magic to me than something I really understand (I mean, roughly and abstractly I actually do understand it, but not in
 a practically useful way).

 One solution I tried to to use was to create an algorithm for "dropping frames", or rather only including frames at
 every n distance; this improved things a lot, but not enough, because the apparent speed around a curve is still much
 slower than over a line, even if those curves are nothing but little lines themselves. I included that solution here.

 What I think would be the ideal case is to reverse-engineer these functions—to make them output points that correspond
 to a certain frame rate. But any solution would really work for me.

 If you wanted to see this in action you could clone https://github.com/jmwmulle/TraceLab, but you'd need the newest
 version of klibs which will require you to brew a few dependencies first and possibly install some business with pip.
 it might be more useful to do so, becuse the animate() method of the DrawFigure class (of which the included def is
 a modification) will also overlay the path the dot is traversing, which I, at least, found much more informative.
 It will also generate the path itself, which is useful because the problems I've described don't rally surface until
 you're joining a variety of segments together.
"""
def pascal_row(n):
	# This returns the nth row of Pascal's Triangle
	result = [1]
	x, numerator = 1, n
	for denominator in range(1, n//2+1):
		# print(numerator,denominator,x)
		x *= numerator
		x /= denominator
		result.append(x)
		numerator -= 1
					  # n is even							  n is odd
		result.extend(reversed(result[:-1]) if n & 1 == 0 else reversed(result))
	return result



def bezier_interpolation(origin, destination, control_o, control_d=None):
		destination = tuple(destination)
		origin = tuple(origin)
		control_o = tuple(control_o)
		if control_d:
			control_d = tuple(control_d)
		points = [origin, control_o, control_d, destination] if control_d else [origin, control_o, destination]
		break_next = False
		segments = []
		n = len(points)

		def bezier(transitions):
			combinations = pascal_row(n - 1)
			result = []
			for t in transitions:
				t_powers = (t ** i for i in range(n))
				u_powers = reversed([(1 - t) ** i for i in range(n)])
				coefficients = [c * a * b for c, a, b in zip(combinations, t_powers, u_powers)]
				result.append(list(sum([coef * p for coef, p in zip(coefficients, ps)]) for ps in zip(*points)))
			return result

		return [ (int(p[0]), int(p[1])) for p in bezier([0.01 * t for t in range(101)])]


def linear_interpolation(origin, destination, segmented=True):
	d_x = destination[0] - origin[0]
	d_y = destination[1] - origin[1]
	theta = angle_between(origin, destination)
	steps = abs(d_x) if abs(d_x) < abs(d_y) else abs(d_y)
	points = [origin]
	for i in range(steps):
		points.append(point_pos(origin, i, theta))
	points.append(destination)
	if segmented:
		segments = list(chunk(points, 2))
		return segments if len(segments[-1]) == 2 else segments[:-1]
	else:
		return points


def path_len(frames):
	# where frames is a list of coordinate tuples
	path_len = 0
	for i in range(0, len(frames)):
		try:
			p1 = [1.0 * frames[i][0], 1.0 * frames[i][1]]
			p2 = [1.0 * frames[i + 1][0], 1.0 * frames[i + 1][1]]
			path_len += line_segment_len(p1, p2)
		except IndexError:
			p1 = [1.0 * frames[i][0], 1.0 * frames[i][1]]
			p2 = [1.0 * frames[0][0], 1.0 * frames[0][1]]
			path_len += line_segment_len(p1, p2)
	return path_len


def animate(self, duration):
		surface = self.render()
		draw_in = float(duration)
		rate = 0.01666666667
		max_frames = int(draw_in / rate)
		delta_d = self.path_len / max_frames
		print draw_in, self.path_len, delta_d
		a_frames = [self.frames[0]]
		seg_len = 0
		for i in range(0, len(self.frames)):
			try:
				p1 = [1.0 * self.frames[i][0], 1.0 * self.frames[i][1]]
				p2 = [1.0 * self.frames[i + 1][0], 1.0 * self.frames[i + 1][1]]
				seg_len += line_segment_len(p1, p2)
			except IndexError:
				p1 = [1.0 * self.frames[i][0], 1.0 * self.frames[i][1]]
				p2 = [1.0 * self.frames[0][0], 1.0 * self.frames[0][1]]
				seg_len += line_segment_len(p1, p2)
			if seg_len >= delta_d:
				a_frames.append(self.frames[i])
				seg_len = 0

		# skip_frame = int(len(frames) / max_frames)
		# removed = 0
		# while len(frames) > max_frames:
		# 	removed += 1
		# 	try:
		# 		frames.remove(frames[removed * skip_frame])
		# 	except IndexError:
		# 		break
		# trunc_frames = [item for index, item in enumerate(frames) if (index + 1) % skip_frame != 0]

		last_f = time.time()
		f = 0
		frame_start = time.time()
		for f in a_frames:
			while time.time() < rate + last_f:
				pump()
			# f += 1
			# pos = a_frames[f]
			self.exp.fill()
			self.exp.blit(surface, 5, Params.screen_c)
			self.exp.blit(self.exp.tracker_dot, 5, f)
			self.exp.flip()
			last_f = time.time()
		print time.time() - frame_start


class TraceLab(klibs.Experiment):
	# graphical elements
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
	response_window_extension = 1 # second
	response_window = None  # speed + constant

	# debug & configuration
	show_drawing = True
	sample_exposure_time = 4500

	# dynamic trial vars
	drawing = []
	figure = None
	figure_dots = None
	figure_segments = None



	def __init__(self, *args, **kwargs):
		super(TraceLab, self).__init__(*args, **kwargs)


	def setup(self):
		# c = bezier_interpolation( (10,10), (100,100), (10, 500), segmented=False)
		# print c
		# surf = aggdraw.Draw("RGBA", (800, 800), (255, 255, 255, 255))
		# p_str = "M10 10"
		# for i in range(0, len(c)):
		# 	try:
		# 		p_str += " L{0} {1} {2} {3}".format(*(list(c[i]) + list(c[i+1])))
		# 	except IndexError:
		# 		pass
		# sym = aggdraw.Symbol(p_str)
		# surf.symbol((0, 0), sym, aggdraw.Pen((255, 0, 0), 1, 255))
		# surf = aggdraw_to_array(surf)
		# self.fill()
		# # for p in c:
		# # 	self.blit(self.tracker_dot)
		# self.blit(surf)
		# self.flip()
		#
		# self.any_key()
		# self.quit()
		#
		# self.canvas = Rectangle(self.canvas_size, fill=self.canvas_color, stroke=[2, self.canvas_border, STROKE_INNER])
		self.origin_proto = Ellipse(self.origin_size)
		self.tracker_dot_proto = Ellipse(self.tracker_dot_size)
		self.tracker_dot_proto.fill = [255, 0, 0]
		self.tracker_dot = self.tracker_dot_proto.render()
		self.text_manager.add_style('instructions', 32, [255, 255, 255, 255])
		self.text_manager.add_style('tiny', 12, [255, 255,255, 255])
		self.figure = DrawFigure(self)
		self.figure.animate(10)
		self.quit()
		self.origin_proto.fill = self.origin_active_color
		self.origin_active = self.origin_proto.render()
		self.origin_proto.fill = self.origin_inactive_color
		self.origin_inactive = self.origin_proto.render()
		self.origin_pos = (Params.screen_c[0], Params.screen_c[1] + self.canvas_size // 2)
		half_or = self.origin_size // 2
		ob_x1 = self.origin_pos[0] - half_or
		ob_y1 = self.origin_pos[1] - half_or
		ob_x2 = self.origin_pos[0] + half_or
		ob_y2 = self.origin_pos[0] + half_or
		self.origin_boundary = [(ob_x1, ob_y1), (ob_x2, ob_y2)]
		self.instructions_1 = "On each trial you will have {0} seconds to study a random figure.\nYou will later be asked to draw it.\nPress any key to begin.".format(self.sample_exposure_time // 1000)
		self.instructions_2 = "Now draw the figure you have just seen.\n - Start by placing the cursor on the red dot. \n - End by placing the cursor on the green dot. \n\nPress any key to proceed."


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
		self.rc.draw_listener.canvas_size = [self.canvas.object_width, self.canvas.object_width]
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
		self.fill()
		self.figure_segments = self.generate_figure()
		Params.clock.register_events([ET('end_exposure', self.sample_exposure_time)])
		self.show_figure()

	def trial(self):
		while self.evi.before('end_exposure', True):
			self.show_figure()
		self.fill()
		self.message(self.instructions_2, 'instructions', registration=5, location=Params.screen_c, flip=True)
		self.any_key()
		self.fill()
		self.rc.collect()
		self.fill()
		self.message("Press any key to begin the next trial.", 'instructions', registration=5, location=Params.screen_c, flip=True)
		self.any_key()
		return {
			"block_num": Params.block_number,
			"trial_num": Params.trial_number,
			"figure": self.figure_segments,
			"drawing": self.rc.draw_listener.responses[0][0],
			"rt": self.rc.draw_listener.responses[0][1]
		}

	def trial_clean_up(self):
		pass

	def clean_up(self):
		pass

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



class DrawFigure(object):

	def __init__(self, exp):
		self.exp = exp
		self.min_spq = Params.avg_seg_per_q[0] - Params.avg_seg_per_q[1]
		self.max_spq = Params.avg_seg_per_q[0] + Params.avg_seg_per_q[1]
		self.min_spf = Params.avg_seg_per_f[0] - Params.avg_seg_per_f[1]
		self.max_spf = Params.avg_seg_per_f[0] + Params.avg_seg_per_f[1]
		if self.min_spf > 4 * self.min_spq > self.max_spf:
			raise ValueError("Impossible min/max values chosen for points per figure/quadrant.")
		self.quad_ranges = None
		self.dot = Ellipse(5, fill=(255,45,45))
		self.r_dot = self.dot.render()
		self.total_spf = 0
		self.points = []
		self.segments = []
		self.frames = None
		self.path_len = 0
		self.__generate_null_points__()
		self.__gen_quad_intersects__()
		self.__gen_real_points__()
		self.__gen_segments__()


	def __generate_null_points__(self):
		# make sure minimums won't exceed randomly generated total
		while 4 * self.min_spq >= self.total_spf <= self.max_spf:
			try:
				self.total_spf = randrange(self.min_spf, self.max_spf)
			except ValueError:
				self.total_spf = self.min_spf

		# give each quadrant it's minimum number of points
		for i in range(0, 4):
			self.points.append([])
			for j in range(0, self.min_spq):
				self.points[i].append(None)

		# distribute the remainder, if any, randomly
		while (self.total_spf - sum([len(q) for q in self.points])) > 0:
			q = randrange(0,4)
			if len(self.points[q]) < self.max_spq:
				self.points[q].append(None)

	def __gen_quad_intersects__(self):
		# replaces the first index of each quadrant in self.points with a coordinate tuple
		i_m = Params.inner_margin
		o_mh = Params.outer_margin_h
		o_mv = Params.outer_margin_v
		s_c = Params.screen_c
		s_x = Params.screen_x
		s_y = Params.screen_y
		self.quad_ranges = [
			[(o_mh, s_c[1] + i_m), (s_c[0] - i_m, s_y - o_mv)],
			[(o_mh, o_mv), (s_c[0] - i_m, s_c[1] - i_m)],
			[(s_c[0] + i_m, o_mv), (s_x - o_mh, s_c[1] - i_m)],
			[(s_c[0] + i_m, s_c[1] + i_m), (s_x - o_mh, s_y - o_mv)]]
		self.points[0][0] = (s_c[0], randrange(s_c[1] + i_m, s_y - o_mv))
		self.points[1][0] = (randrange(o_mh, s_c[0] - i_m), s_c[1])
		self.points[2][0] = (s_c[0], randrange(o_mv, s_c[1] - i_m))
		self.points[3][0] = (randrange(s_c[0] + i_m, s_x - o_mh), s_c[1])


	def __gen_real_points__(self):
		for i in range(0, 4):
			for j in range(1, len(self.points[i])):
				x = randrange(self.quad_ranges[i][0][0], self.quad_ranges[i][1][0])
				y = randrange(self.quad_ranges[i][0][1], self.quad_ranges[i][1][1])
				self.points[i][j] = (x, y)
		self.points = list(chain(*self.points))

	def __gen_segments__(self):
		for i in range(0, len(self.points)):
			curves = int((1.0 - Params.angularity) * 10) * [False]
			lines = int(Params.angularity * 10) * [True]
			if choice(curves+lines):
				try:
					self.segments.append(linear_interpolation(self.points[i], self.points[i + 1], segmented=False))
				except IndexError:
					self.segments.append(linear_interpolation(self.points[i], self.points[0], segmented=False))
			else:
				try:
					amp = line_segment_len(self.points[i], self.points[i + 1])
					r = angle_between(self.points[i], self.points[i + 1])
					c = point_pos(midpoint(self.points[i], self.points[i + 1]), amp, 90, r)
					self.segments.append(bezier_interpolation(self.points[i], self.points[i + 1], c))
				except IndexError:
					amp = line_segment_len(self.points[i], self.points[0])
					c = point_pos(midpoint(self.points[i], self.points[0]), amp, 90)
					self.segments.append(bezier_interpolation(self.points[i], self.points[0], c))
		self.frames = list(chain(*self.segments))
		for i in range(0, len(self.frames)):
			try:
				p1 = [1.0 * self.frames[i][0], 1.0 * self.frames[i][1]]
				p2 = [1.0 * self.frames[i + 1][0], 1.0 * self.frames[i + 1][1]]
				self.path_len += line_segment_len(p1, p2)
			except IndexError:
				p1 = [1.0 * self.frames[i][0], 1.0 * self.frames[i][1]]
				p2 = [1.0 * self.frames[0][0], 1.0 * self.frames[0][1]]
				self.path_len += line_segment_len(p1, p2)


	def render(self):
		surf = aggdraw.Draw("RGBA", Params.screen_x_y, Params.default_fill_color)
		p_str = "M{0} {1}".format(*self.frames[0])
		for s in chunk(self.frames, 2):
			try:
				p_str += " L{0} {1} {2} {3}".format(*(list(s[0]) + list(s[1])))
			except IndexError:
				pass
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0, 0), sym, aggdraw.Pen((35, 35, 35), 0.5, 255))
		return aggdraw_to_array(surf)

	def draw(self, dots=True, flip=True):
		self.exp.fill()
		self.exp.blit(self.render())
		if dots:
			for p in self.points:
				self.exp.blit(self.r_dot, 5, p)
				self.exp.message(str(p[0]), "tiny", location=p)
		if flip:
			self.exp.flip()


	def animate(self, duration):

		surface = self.render()
		draw_in = float(duration)
		rate = 0.01666666667
		max_frames = int(draw_in / rate)
		delta_d = self.path_len / max_frames
		print draw_in, self.path_len, delta_d
		a_frames = [self.frames[0]]
		seg_len = 0
		for i in range(0, len(self.frames)):
			try:
				p1 = [1.0 * self.frames[i][0], 1.0 * self.frames[i][1]]
				p2 = [1.0 * self.frames[i + 1][0], 1.0 * self.frames[i + 1][1]]
				seg_len += line_segment_len(p1, p2)
			except IndexError:
				p1 = [1.0 * self.frames[i][0], 1.0 * self.frames[i][1]]
				p2 = [1.0 * self.frames[0][0], 1.0 * self.frames[0][1]]
				seg_len += line_segment_len(p1, p2)
			if seg_len >= delta_d:
				a_frames.append(self.frames[i])
				seg_len = 0

		# skip_frame = int(len(frames) / max_frames)
		# removed = 0
		# while len(frames) > max_frames:
		# 	removed += 1
		# 	try:
		# 		frames.remove(frames[removed * skip_frame])
		# 	except IndexError:
		# 		break
		# trunc_frames = [item for index, item in enumerate(frames) if (index + 1) % skip_frame != 0]

		last_f = time.time()
		f = 0
		frame_start = time.time()
		for f in a_frames:
			while time.time() < rate + last_f:
				pump()
			# f += 1
			# pos = a_frames[f]
			self.exp.fill()
			self.exp.blit(surface, 5, Params.screen_c)
			self.exp.blit(self.exp.tracker_dot, 5, f)
			self.exp.flip()
			last_f = time.time()
		print time.time() - frame_start