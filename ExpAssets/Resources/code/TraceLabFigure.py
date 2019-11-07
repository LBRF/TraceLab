# -*- coding: utf-8 -*-
__author__ = 'Jonathan Mulle & Austin Hurst'

import os
import io
import math
from itertools import chain
from random import random, randrange, uniform, choice, shuffle

import zipfile
import aggdraw
import numpy as np
from PIL import Image

from klibs.KLExceptions import TrialException
from klibs.KLEnvironment import EnvAgent
import klibs.KLParams as P
from klibs.KLBoundary import RectangleBoundary
from klibs.KLTime import precise_time as time
from klibs.KLUtilities import (angle_between, acute_angle, point_pos, indices_of, scale, now, utf8,
	line_segment_len)
from klibs.KLUserInterface import ui_request
from klibs.KLGraphics import blit, flip, fill
from klibs.KLGraphics.KLDraw import Ellipse
from klibs.KLCommunication import message

from drawingutils import (bezier_length, bezier_bounds, linear_intersection,
	bezier_transitions_by_dist, bezier_interpolation,
	linear_transitions_by_dist, linear_interpolation)


def frames_to_path(frames, unique=False):
	"""Renders a list of (x, y) tuples representing the frames of a figure into an
	aggdraw Path object for drawing.
	"""
	path = aggdraw.Path()
	path.moveto(frames[0][0], frames[0][1]) # start at first point

	prev = frames[0]
	for f in frames:
		# If current frame not different than previous one, discard it
		if unique and (f[0] == prev[0] and f[1] == prev[1]):
			continue
		path.lineto(f[0], f[1])
		prev = f

	path.close()
	return path


def segments_to_symbol(segments):
	"""Renders a list of curve and line segments into an aggdraw Path object for drawing.
	"""

	path = "M{0},{1} ".format(segments[0][1][0][0], segments[0][1][0][1]) # start at first point
	for curve, points in segments:
		if curve:
			start, end, ctrl = points
			path += "Q{0},{1},{2},{3} ".format(ctrl[0], ctrl[1], end[0], end[1])
		else:
			start, end = points
			path += "L{0},{1} ".format(end[0], end[1])

	return aggdraw.Symbol(path)



class TraceLabFigure(EnvAgent):

	allow_verbosity = False

	def __init__(self, import_path=None, animate_time=5000.0, manufacture=None):

		self.animate_target_time = animate_time
		self.seg_count = None
		self.min_spq = P.avg_seg_per_q[0] - P.avg_seg_per_q[1]
		self.max_spq = P.avg_seg_per_q[0] + P.avg_seg_per_q[1]
		self.min_spf = P.avg_seg_per_f[0] - P.avg_seg_per_f[1]
		self.max_spf = P.avg_seg_per_f[0] + P.avg_seg_per_f[1]

		# segment generation controls
		self.min_lin_ang_width = P.min_linear_acuteness * 180
		min_shift_size = int(P.peak_shift[0] * 1000) # TODO: fix this mess
		max_shift_size = int(P.peak_shift[1] * 1000)
		self.peak_shift_range = [i / 1000.0 for i in range(min_shift_size, max_shift_size)]

		min_curve_sheer = int(P.curve_sheer[0] * 9000) # TODO: fix this mess
		max_curve_sheer = int(P.curve_sheer[1] * 9000)
		self.c_sheer_range = [i / 100.0 for i in range(min_curve_sheer, max_curve_sheer)]
		self.curve_min_slope = int(math.floor(90.0 - P.slope_magnitude[0] * 90.0))
		self.curve_max_slope = int(math.ceil(90.0 + P.slope_magnitude[0] * 90.0))

		if self.min_spf > 4 * self.min_spq > self.max_spf:
			raise ValueError("Impossible min/max values chosen for points per figure/quadrant.")
		if P.outer_margin_h + P.inner_margin_h // 2 > P.screen_c[0]:
			raise ValueError("Margins too large; no drawable area remains.")
		if P.outer_margin_v + P.inner_margin_v // 2 > P.screen_c[1]:
			raise ValueError("Margins too large; no drawable area remains.")

		self.quad_ranges = None
		self.r_dot = Ellipse(5, fill=(255, 45, 45)).render()
		self.total_spf = 0
		self.points = []
		self.raw_segments = []
		self.a_frames = []  # interpolated frames tracing figure at given duration / fps
		self.trial_a_frames = []  # a_frames plus frame onset times for previous animation
		self.width = P.screen_x - (2 * P.outer_margin_h)  # NOTE: This isn't actually used anywhere
		self.height = P.screen_y - (2 * P.outer_margin_v)  # NOTE: This isn't actually used anywhere
		self.screen_res = [P.screen_x, P.screen_y]
		self.avg_velocity = None  # last call to animate only
		self.animate_time = None  # last call to animate only
		self.rendered = False

		if import_path:
			self.__import_figure(import_path)
		elif manufacture:
			self.points = manufacture['points']
			self.seg_count = len(self.points)
			self.raw_segments = manufacture['segments']
		else:
			self.__generate_null_points()
			self.__gen_quad_intersects()
			self.__gen_real_points(not P.generate_quadrant_intersections)
			self.__gen_segments()

		self.prepare_animation(duration=5000.0) # pre-render animation frames at slowest rate


	def __import_figure(self, path):

		# Open the figure archive and find the .tlf file containing the figure data
		fig_archive = zipfile.ZipFile(path + ".zip")
		figure = path.split("/")[-1]
		fig_file = figure + ".tlf"
		if fig_file not in fig_archive.namelist():
			fig_file = figure + "/" + fig_file

		# Import figure attributes from .tlf and make attributes of current figure object
		figure_res = [1920, 1080]
		with fig_archive.open(fig_file) as tlf:
			for l in io.TextIOWrapper(tlf, 'utf8'):
				attr = l.split(" = ")
				if len(attr):
					if attr[0] in ['raw_segments', 'points']:
						setattr(self, attr[0], eval(attr[1]))
					elif attr[0] == 'screen_res':
						figure_res = eval(attr[1])

		# Prepare figure segment data for re-interpolation, scaling pixel coordinates if necessary
		self.seg_count = len(self.points)
		self.points = [scale(p, figure_res) for p in self.points]
		for i in range(len(self.raw_segments)):
			points = self.raw_segments[i][1]
			points = points[:-1] if isinstance(points[-1], int) else points  # fix for old .tlfs
			self.raw_segments[i][0] = len(points) == 3  # fix line/curve id for old .tlfs
			self.raw_segments[i][1] = tuple([scale(p, figure_res) for p in points])


	def __generate_null_points(self):

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
			q = randrange(0, 4)
			if len(self.points[q]) < self.max_spq:
				self.points[q].append(None)


	def __gen_quad_intersects(self):

		# replaces the first index of each quadrant in self.points with a coordinate tuple
		i_mv = P.inner_margin_v
		i_mh = P.inner_margin_h
		o_mh = P.outer_margin_h
		o_mv = P.outer_margin_v
		s_c = P.screen_c
		s_x = P.screen_x
		s_y = P.screen_y

		self.quad_ranges = [
			[(o_mh, s_c[1] + i_mv), (s_c[0] - i_mh, s_y - o_mv)],
			[(o_mh, o_mv), (s_c[0] - i_mh, s_c[1] - i_mv)],
			[(s_c[0] + i_mh, o_mv), (s_x - o_mh, s_c[1] - i_mv)],
			[(s_c[0] + i_mh, s_c[1] + i_mv), (s_x - o_mh, s_y - o_mv)]
		]
		if P.generate_quadrant_intersections:
			self.points[0][0] = (s_c[0], randrange(s_c[1] + i_mv, s_y - o_mv))
			self.points[1][0] = (randrange(o_mh, s_c[0] - i_mh), s_c[1])
			self.points[2][0] = (s_c[0], randrange(o_mv, s_c[1] - i_mv))
			self.points[3][0] = (randrange(s_c[0] + i_mh, s_x - o_mh), s_c[1])


	def __gen_real_points(self, overwrite_intersections=False):

		start_index = 0 if overwrite_intersections else 1
		for i in range(0, 4):
			for j in range(start_index, len(self.points[i])):
				x = randrange(self.quad_ranges[i][0][0], self.quad_ranges[i][1][0])
				y = randrange(self.quad_ranges[i][0][1], self.quad_ranges[i][1][1])
				self.points[i][j] = (x, y)
		self.points = list(chain(*self.points))
		self.seg_count = len(self.points)


	def __gen_segments(self):

		# first generate the segments to establish a path length
		first_pass_segs = []  # ie. raw interpolation unadjusted for velocity
		#segment_types = [random() > P.angularity for i in range(len(self.points))]
		seg_type_dist = int((1.0 - P.angularity) * 10) * [True] + int(P.angularity * 10) * [False]
		segment_types = [choice(seg_type_dist)] * len(self.points)

		i = 0
		i_linear_fail = False
		i_curved_fail = False
		start = time()
		while len(segment_types):

			s = segment_types.pop()
			p1 = self.points[i]
			p2 = self.points[(i + 1) if (i + 1) < len(self.points) else 0]

			if P.verbose_mode and self.allow_verbosity:
				fmt = [i, "curve" if s else "line", (p1, p2)]
				print("Starting segment {0} of {2} ({1})".format(*fmt))

			try:
				if not s:  # ie. not curve
					if len(first_pass_segs) == 0:
						segment = [False, (p1, p2)]
						seg_ok = True
					else:
						seg_ok = False
					while not seg_ok:
						prev_seg = first_pass_segs[-1]
						if time() - start > P.generation_timeout:
							raise RuntimeError("Figure generation timed out (1).")
						if P.verbose_mode and self.allow_verbosity:
							print("{0} of {1}".format(i + 1, len(self.points)))
						ui_request()
						segment = self.__generate_linear_segment(p1, p2, prev_seg)
						if all(type(n) is int for n in segment):
							if not len(segment_types):
								raise TrialException("Can't change origin location.")
							p2 = segment
						else:
							seg_ok = True
				else:
					segment = self.__generate_curved_segment(p1, p2)
					# If bezier control point same as start or end points, just make segment linear
					start, end, ctrl = segment[1]
					if start == ctrl or end == ctrl:
						segment = [False, (start, end)]

				first_pass_segs.append(segment)
				i += 1
				i_curved_fail = False
				i_linear_fail = False
				if P.verbose_mode and self.allow_verbosity:
					print("Segment {0} done ({1})".format(i, "curve" if s else "line"))
			except TrialException:
				e = "Generation failed on {0} segment.".format("curved" if s else "linear")
				print(e)
				if len(segment_types) > 0 and not all(t == s for t in segment_types):
					if s:
						i_curved_fail = True
					else:
						i_linear_fail = True
					if i_curved_fail and i_linear_fail:
						raise RuntimeError(e)  # no suitable segment can be drawn between these pts
					segment_types.append(s)
					shuffle(segment_types)
				else:
					raise RuntimeError(e)
		self.raw_segments = first_pass_segs


	def __generate_linear_segment(self, p1, p2, prev_seg=None):

		if prev_seg and prev_seg[0] == False:
			p_prev = prev_seg[1][0]
			#  if the angle is too acute, try to shift p2 a way from prev_seg until it's ok
			seg_angle = acute_angle(p1, p_prev, p2)
			if seg_angle < self.min_lin_ang_width:
				print(seg_angle, self.min_lin_ang_width, p1, p_prev, p2)
				p2 = list(p2)

				a_p1_prev = angle_between(p1, p_prev)
				a_prev_p2 = angle_between(p_prev, p2, a_p1_prev)
				len_prev_p2 = line_segment_len(p_prev, p2)
				p2 = point_pos(p_prev, len_prev_p2 + 1, a_prev_p2, a_p1_prev)
				if p2[0] < 0 or p2[0] > P.screen_x or p2[1] < 0 or p2[1] > P.screen_y:
					raise TrialException("No appropriate angle can be generated.")
				else:
					return p2

		return [False, (p1, p2)]


	def __generate_curved_segment(self, p1, p2):

		# single letters here mean: r = rotation, c = control, p = point, q = quadrant, a = angle, v = vector

		#  reference p is the closer of p1, p2 to the screen center for the purposes of determining direction and angle
		p_ref = p1
		if line_segment_len(p1, P.screen_x_y) > line_segment_len(p2, P.screen_x_y):
			p_ref = p2

		# gets the radial rotation between p1 and p2
		r = angle_between(p_ref, p2 if p_ref == p1 else p1)

		#  depending on the qudrant, p1->p2
		q = self.__quadrant_from_point(p1)
		if len(q) > 1:  # if p1 is directly on an axis line an ambiguous answer is returned; check p2 instead
			q = self.__quadrant_from_point(p2)

		# decides the radial direction from p1->p2, clockwise or counterclockwise, from which the curve will extend
		c_spin = choice([True, False])
		if P.verbose_mode and self.allow_verbosity:
			print("p_ref: {0}\nr: {1}\nq: {2}\n c_spin: {3}".format(p_ref, r, q, c_spin))

		#  find linear distance between p1 and p2
		d_p1p2 = line_segment_len(p1, p2)
		if P.verbose_mode and self.allow_verbosity:
			print("seg_line_len: {0}\nasym_max: {1}\nasym_min: {2}".format(d_p1p2, self.asym_max, self.asym_min))

		#  next lines decide location of the perpendicular extension from control point and p1->p2
		c_base_shift = choice(self.peak_shift_range) * d_p1p2
		#c_base_shift = uniform(P.peak_shift[0], P.peak_shift[1]) * d_p1p2
		c_base_amp = c_base_shift if choice([1, 0]) else d_p1p2 - c_base_shift  # ensure shift not always away from p_ref
		p_c_base = point_pos(p_ref, c_base_amp, r)
		if P.verbose_mode and self.allow_verbosity: 
			print("c_base_amp: {0}\np_c_base: {1}".format(c_base_amp, p_c_base))

		#  the closer of p1, p2 to p_c_base will be p_c_ref when determining p_c_min
		if c_base_amp > 0.5 * d_p1p2:
			p_c_ref = p2 if p_ref == p1 else p1
		else:
			p_c_ref = p2 if p_ref == p2 else p1

		# choose an angle, deviating from 90 (+/-) by some random value, for p_c_ref -> p_c_base -> p_c
		try:
			sheer = choice(self.c_sheer_range) #uniform(P.curve_sheer[0], P.curve_sheer[1]) * 90
		except IndexError:
			sheer = 0
		a_c = 90 + sheer if choice([0, 1]) else 90 - sheer

		if P.verbose_mode and self.allow_verbosity:
			txt = "P.curve_sheer: {3}, c_angle_max: {0}\nc_angle_min: {1}\nc_angle: {2}"
			print(txt.format(self.a_c_min, self.a_c_max, a_c, P.curve_sheer))

		#  get the range of x,y values for p_c
		v_c_base = [p_c_base, a_c, r, c_spin]  # ie. p_c_base as origin
		v_c_min = [p_c_ref, self.curve_min_slope, r, not c_spin]  # ie. p_c_ref as origin
		v_c_max = [p_c_ref, self.curve_max_slope, r, not c_spin]  # ie. p_c_ref as origin
		p_c_min = linear_intersection(v_c_min, v_c_base)
		p_c_max = linear_intersection(v_c_max, v_c_base)
		if P.verbose_mode and self.allow_verbosity:
			txt = "v_c_min: {0}\nv_c_max: {1}\np_c_min: {2}\np_c_max: {3}"
			print(txt.format(v_c_min, v_c_max, p_c_min, p_c_max))

		# choose an initial p_c; depending on quadrant, no guarantee x,y values in p_c_min are less than p_c_max
		try:
			p_c_x = randrange(p_c_min[0], p_c_max[0])
		except ValueError:
			try:
				p_c_x = randrange(p_c_max[0], p_c_min[0])
			except ValueError:
				p_c_x = p_c_min[0]
		try:
			p_c = (p_c_x, randrange(p_c_min[1], p_c_max[1]))
		except ValueError:
			try:
				p_c = (p_c_x, randrange(p_c_max[1], p_c_min[1]))
				p_c = (p_c_x, randrange(p_c_max[1], p_c_min[1]))
			except ValueError:
				p_c = (p_c_x, p_c_max[1])

		#min_x, max_x = sorted([p_c_min[0], p_c_max[0]])
		#min_y, max_y = sorted([p_c_min[1], p_c_max[1]])
		#p_c_x = min_x if min_x == max_x else randrange(min_x, max_x)
		#p_c_y = min_y if min_y == max_y else randrange(min_y, max_y)
		#p_c = (p_c_x, p_c_y)

		# Make sure the generated bezier curve doesn't go off the screen, adjusting if necessary
		v_c_b_len = line_segment_len(p_c_ref, p_c)
		v_c_b_increment = -1
		cmx, cmy = (P.curve_margin_h, P.curve_margin_v)
		screen_bounds = RectangleBoundary(' ', (cmx, cmy), (P.screen_x - cmx, P.screen_y - cmy))
		prev_err = 0
		failures = 0
		segment = False
		while not segment:

			bounds = bezier_bounds(p1, p_c, p2)
			if all([screen_bounds.within(p) for p in bounds]):
				segment = True

			else:
				# After initial pass, check if bezier adjustment making bounds closer
				# or further from being fully on-screen. If getting worse, change direction
				# of the adjustment.
				failures += 1
				err_x1, err_x2 = (-bounds[0][0], bounds[1][0] - P.screen_x)
				err_y1, err_y2 = (-bounds[0][1], bounds[1][1] - P.screen_y)
				err = max(err_x1, err_x2, err_y1, err_y2)

				if failures > 2:
					if err > prev_err:
						if v_c_b_increment < 0:
							v_c_b_increment = 1
							v_c_b_len += 1
						else:
							raise RuntimeError("Unable to adjust curve to fit on screen.")
					elif failures == 3:
						# If error getting smaller after initial shift and decrement, use rate of
						# decrease in boundary error per decrease in v_c_b_len to estimate what the
						# v_c_b_len for for an error of 0 should be and jump to that.
						v_c_b_len += v_c_b_increment * int(err / (prev_err - err))
						v_c_b_len -= v_c_b_increment

				# NOTE: this very likely doesn't work as intended; completely changes curve
				# instead of adjusting to fit within screen
				v_c_b_len += v_c_b_increment
				p_c = point_pos(p_c_base, v_c_b_len, a_c, r, c_spin, return_int=False)
				prev_err = err

			if (P.verbose_mode and self.allow_verbosity):
				msg = "Curve {0}, ".format("succeeded" if segment else "failed")
				pts = "p1:{0}, p2: {1}, p_c: {2}, v_c_b_len: {3}".format(p1, p2, p_c, v_c_b_len)
				print(msg + pts)
				if not segment:
					print("Curve bounds: p1 = {0}, p2 = {1}".format(bounds[0], bounds[1]))

		return [True, (p1, p2, p_c)]


	def __quadrant_from_point(self, point):

		q = [True, True, True, True]

		if point[0] > P.screen_c[0]:
			q[0] = False
			q[1] = False

		if point[0] < P.screen_c[0]:
			q[2] = False
			q[3] = False

		if point[1] > P.screen_c[1]:
			q[1] = False
			q[2] = False

		if point[1] < P.screen_c[1]:
			q[0] = False
			q[3] = False

		return indices_of(True, q, True)


	def segments_to_frames(self, segments, duration, fps=60):
		"""Converts linear/bezier segments comprising a shape into a list of (x, y) pixel
		coordinates representing the frames of the shape animation at the given velocity.

		Args:
			segments (list): A list of linear and/or bezier segments generated by the
				__generate_linear_segment and __generate_curved_segment functions.
			duration (float): The duration the tracing motion in milliseconds.
			fps (float, optional): The frame rate at which to render the frames.
		"""

		total_frames = int(round(duration / (1000.0 / fps)))
		dist_per_frame = self.path_length / total_frames

		offset = 0
		fig_frames = []
		for curve, points in segments:

			if curve:
				start, end, ctrl = points
				dist = bezier_length(start, ctrl, end)
				transitions = bezier_transitions_by_dist(start, ctrl, end, dist_per_frame, offset)
				fig_frames += bezier_interpolation(start, end, ctrl, transitions)
			else:
				start, end = points
				dist = line_segment_len(start, end)
				transitions = linear_transitions_by_dist(start, end, dist_per_frame, offset)
				fig_frames += linear_interpolation(start, end, transitions)

			frames = len(transitions) - 1
			offset = (frames + 1) * dist_per_frame - (dist - offset)

		return fig_frames


	def render(self, trace=None, smooth=True):
		"""Renders the figure (and optionally a provided participant tracing) to a numpy array
		texture that can be drawn to the screen.

		Args:
			trace (list, optional): A list of (x, y) tuples containing a participant tracing to be
				drawn on top of the figure.
			smooth (bool, optional): A flag indicating whether to draw the figure smoothly or by
				drawing lines between the frames from the last prepare_animation call. Defaults to
				True.
		"""

		# Initialize drawing surface
		canvas = Image.new("RGBA", P.screen_x_y, (0, 0, 0, 255))
		surf = aggdraw.Draw(canvas)

		# Draw figure to surface
		if smooth:
			s = segments_to_symbol(self.raw_segments)
			surf.symbol((0, 0), s, aggdraw.Pen(P.stimulus_feedback_color, 1, 255))
		else:
			path = frames_to_path(self.a_frames, unique=True)
			surf.path(path, aggdraw.Pen(P.stimulus_feedback_color, 1, 255))

		# If tracing, draw trace to surface too
		if trace:
			path = frames_to_path(trace, unique=True)
			surf.path(path, aggdraw.Pen(P.response_feedback_color, 1, 255))

		# Render to numpy array and return
		surf.flush()
		self.rendered = np.asarray(canvas)
		return self.rendered


	def draw(self, dots=True):

		path_len = round(self.path_length, 1)
		msg = message("Path Length: {0} pixels".format(path_len), blit_txt=False)

		blit(self.render(smooth=True), flip_x=P.flip_x)
		blit(msg, 1, (30, P.screen_y - 25))
		if dots:
			for p in self.points:
				blit(self.r_dot, 5, p, flip_x=P.flip_x)
				message("({0}, {1})".format(*p), "tiny", registration=7, location=p, blit_txt=True)


	def prepare_animation(self, duration=None):

		if duration is None:
			duration = self.animate_target_time

		self.a_frames = self.segments_to_frames(self.raw_segments, duration, fps=P.refresh_rate)


	def animate(self):

		start = None
		updated_a_frames = []
		for f in self.a_frames:

			ui_request()
			fill()
			if P.demo_mode:
				blit(self.rendered, 5, P.screen_c, flip_x=P.flip_x)
			blit(self.exp.tracker_dot, 5, f, flip_x=P.flip_x)
			flip()

			if start is None:
				timestamp = 0.0
				start = time()
			else:
				timestamp = time() - start
			updated_a_frames.append((f[0], f[1], timestamp))

		self.trial_a_frames = updated_a_frames


	def write_out(self, file_name, trial_data=None):

		writing_tracing = trial_data is not None
		if not trial_data:
			trial_data = self.trial_a_frames

		points_file_name = file_name[:-4] + ".tlfp"
		segments_file_name = file_name[:-4] + ".tlfs"
		ext_interp_file_name = file_name[:-4] + ".tlfx"
		thumb_file_name = file_name[:-4] + "_preview.png"
		thumbx_file_name = file_name[:-4] + "_ext_preview.png"

		fig_path = os.path.join(self.exp.fig_dir, file_name)
		points_path = os.path.join(self.exp.fig_dir, points_file_name)
		segments_path = os.path.join(self.exp.fig_dir, segments_file_name)
		ext_interpolation_path = os.path.join(self.exp.fig_dir, ext_interp_file_name)
		thumb_path = os.path.join(self.exp.fig_dir, thumb_file_name)
		thumbx_path = os.path.join(self.exp.fig_dir, thumbx_file_name)

		with zipfile.ZipFile(fig_path[:-3] + "zip", "a", zipfile.ZIP_DEFLATED) as fig_zip:

			with io.open(fig_path, "w+", encoding='utf-8') as f:
				if P.capture_figures_mode:
					for k, v in self.__dict__.items():
						if k in ["dot", "r_dot", "exp", "rendered", "a_frames", "trial_a_frames"]:
							continue
						f.write(u"{0} = {1}\n".format(k, v))
				else:
					f.write(utf8(trial_data))

			if P.gen_tlfx and not writing_tracing:
				with io.open(ext_interpolation_path, "w+", encoding='utf-8') as f:
					ext = self.segments_to_frames(self.raw_segments, 5000.0, fps=P.refresh_rate)
					f.write(utf8(ext))
				fig_zip.write(ext_interpolation_path, ext_interp_file_name)
				os.remove(ext_interpolation_path)

			if P.gen_tlfp and not writing_tracing:
				with io.open(points_path, "w+", encoding='utf-8') as f:
					f.write(utf8(self.points))
				fig_zip.write(points_path, points_file_name)
				os.remove(points_path)

			if P.gen_tlfs and not writing_tracing:
				with io.open(segments_path, "w+", encoding='utf-8') as f:
					f.write(u",".join(utf8(s[1]) for s in self.raw_segments))
				fig_zip.write(segments_path, segments_file_name)
				os.remove(segments_path)

			if P.gen_png and not writing_tracing:
				Image.fromarray(self.render()).save(thumb_path, 'PNG')
				fig_zip.write(thumb_path, thumb_file_name)
				os.remove(thumb_path)

			if P.gen_ext_png and not writing_tracing:
				Image.fromarray(self.render(smooth=True)).save(thumbx_path, 'PNG')
				fig_zip.write(thumbx_path, thumbx_file_name)
				os.remove(thumbx_path)

			fig_zip.write(fig_path, file_name)
			os.remove(fig_path)


	@property
	def path_length(self):
		"""float: The full length of the figure in pixels.
		"""
		length = 0
		for curve, points in self.raw_segments:
			if curve:
				p1, p2, ctrl = points
				length += bezier_length(p1, ctrl, p2)
			else:
				p1, p2 = points
				length += line_segment_len(p1, p2)

		return length
