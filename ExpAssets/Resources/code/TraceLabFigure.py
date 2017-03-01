# -*- coding: utf-8 -*-
__author__ = 'jono'
# import klibs.KLParams as P
import os
from itertools import chain
from PIL import ImagePath, ImageDraw, Image
import png
import zipfile
import aggdraw
from klibs.KLGraphics import aggdraw_to_array, blit, flip, fill
from math import ceil, floor
from random import randrange, choice, shuffle
import time
from klibs.KLExceptions import TrialException
import klibs.KLParams as P
from klibs.KLUtilities import *
from klibs.KLGraphics.KLDraw import Ellipse
from klibs.KLUserInterface import ui_request
from klibs. KLCommunication import message
from klibs.KLEnvironment import EnvAgent


def pascal_row(n):
	# This returns the nth row of Pascal's Triangle
	result = [1]
	x, numerator = 1, n
	for denominator in range(1, n // 2 + 1):
		# print(numerator,denominator,x)
		x *= numerator
		x /= denominator
		result.append(x)
		numerator -= 1
		# n is even							  n is odd
		result.extend(reversed(result[:-1]) if n & 1 == 0 else reversed(result))
	return result


global drawable_area

"""
Velocity is measured in (whatever units your distance function uses)/(draw call)
dt is time between draw calls
"""


def linear_interpolation(origin, destination, velocity=None, dt=0.01666667):
	# Ensure the point travels along straight segments at the expected velocity
	angle = angle_between(origin, destination)
	distance = line_segment_len(origin, destination)
	time_to_complete = distance / velocity
	###
	steps = int(time_to_complete / dt)  # abs(d_x) if abs(d_x) < abs(d_y) else abs(d_y)
	step_size = distance / steps
	points = [origin]
	for i in range(steps):
		points.append(point_pos(origin, i * step_size, angle))
	points.append(destination)
	# if segmented:
	# 	segments = list(chunk(points, 2))
	# 	return segments if len(segments[-1]) == 2 else segments[:-1]
	# else:
	return points


"""
Velocity is measured in (whatever units your distance function uses)/(draw call) dt is time between draw calls
"""


def bezier_interpolation(origin, destination, control_o, control_d=None, velocity=None, dt=0.016666666667):
	global drawable_area
	destination = tuple(destination)
	origin = tuple(origin)
	control_o = tuple(control_o)
	if control_d:
		control_d = tuple(control_d)
	points = [origin, control_o, control_d, destination] if control_d else [origin, control_o, destination]
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

	# Estimate the length of the curve
	first_guess = bezier([0.01 * t for t in range(101)])
	for i in first_guess:
		if i[0] < 0 or i[0] > P.screen_x or i[1] < 0 or i[1] > P.screen_y:
			return False
	length_of_first_guess = interpolated_path_len(first_guess)
	if not velocity:
		return [length_of_first_guess, [origin, destination, control_o, control_d]]
	# Calculate the time to traverse the curve at expected velocity
	time_to_completion = length_of_first_guess / velocity
	# The ceil call here biases long
	# If you want to resolve issues of dt not dividing time to complete
	# another way, feel free. The shorter the lines relative to the
	# velocity, the more error this introduces.
	steps = int(math.ceil(time_to_completion / dt))
	# The +1 ensures we get to the end
	final_curve = bezier([t / float(steps) for t in range(steps + 1)])

	return [(int(p[0]), int(p[1])) for p in final_curve]


class TraceLabFigure(EnvAgent):
	allow_verbosity = False

	def __init__(self, import_path=None, animate_time=None, manufacture=None):
		self.animate_target_time = animate_time if animate_time else self.exp.animate_time
		self.seg_count = None
		self.min_spq = P.avg_seg_per_q[0] - P.avg_seg_per_q[1]
		self.max_spq = P.avg_seg_per_q[0] + P.avg_seg_per_q[1]
		self.min_spf = P.avg_seg_per_f[0] - P.avg_seg_per_f[1]
		self.max_spf = P.avg_seg_per_f[0] + P.avg_seg_per_f[1]
		self.extended_interpolation = []  # regardless of real draw time, stores interpolation at 5s for data analysis

		# segment generation controls
		self.min_lin_ang_width = P.min_linear_acuteness * 180
		min_shift_size = int(P.peak_shift[0] * 1000)
		max_shift_size = int(P.peak_shift[1] * 1000)
		self.peak_shift_range = [i / 1000.0 for i in range(min_shift_size, max_shift_size)]

		min_curve_sheer = int(P.curve_sheer[0] * 9000)
		max_curve_sheer = int(P.curve_sheer[1] * 9000)
		self.c_sheer_range = [i / 100.0 for i in range(min_curve_sheer, max_curve_sheer)]
		self.curve_min_slope = int(floor(90.0 - P.slope_magnitude[0] * 90.0))
		self.curve_max_slope = int(ceil(90.0 + P.slope_magnitude[0] * 90.0))

		if self.min_spf > 4 * self.min_spq > self.max_spf:
			raise ValueError("Impossible min/max values chosen for points per figure/quadrant.")
		if P.outer_margin_h + P.inner_margin_h // 2 > P.screen_c[0]:
			raise ValueError("Margins too large; no drawable area remains.")
		if P.outer_margin_v + P.inner_margin_v // 2 > P.screen_c[1]:
			raise ValueError("Margins too large; no drawable area remains.")
		self.quad_ranges = None
		self.dot = Ellipse(5, fill=(255, 45, 45))
		self.r_dot = self.dot.render()
		self.total_spf = 0
		self.points = []
		self.raw_segments = []
		self.segments = []
		self.frames = None  # complete interpolated path
		self.a_frames = None  # interpolation minus dropped frames to ensure constant velocity
		self.path_length = 0
		self.p_len = 0
		self.width = P.screen_x - (2 * P.outer_margin_h)
		self.height = P.screen_y - (2 * P.outer_margin_h)
		self.avg_velocity = None  # last call to animate only
		self.animate_time = None  # last call to animate only
		self.rendered = False
		if import_path:
			self.__import_figure__(import_path)
			return
		if manufacture:
			self.points = manufacture['points']
			self.seg_count = len(self.points)
			for s in manufacture['segments']:
				try:
					path_len = bezier_interpolation(s[0], s[1], s[2])[0]
					self.segments.append(bezier_interpolation(s[0], s[1], s[2], velocity=path_len / s[3]))
				except (IndexError, TypeError):
					self.segments.append(linear_interpolation(s[0], s[1], line_segment_len(s[0], s[1]) / s[2]))
			self.frames = list(chain(*self.segments))
		else:
			self.__generate_null_points__()
			self.__gen_quad_intersects__()
			self.__gen_real_points__(not P.generate_quadrant_intersections)
			self.__gen_segments__()
			self.segments_to_frames()
		# self.extended_interpolation = self.frames
		# self.frames = []
		# self.segments = []
		# self.animate_target_time =
		# self.segments_to_frames()
		# # self.__gen_segments__()

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
			q = randrange(0, 4)
			if len(self.points[q]) < self.max_spq:
				self.points[q].append(None)

	def __gen_quad_intersects__(self):
		global drawable_area
		# replaces the first index of each quadrant in self.points with a coordinate tuple
		i_mv = P.inner_margin_v
		i_mh = P.inner_margin_h
		o_mh = P.outer_margin_h
		o_mv = P.outer_margin_v
		s_c = P.screen_c
		s_x = P.screen_x
		s_y = P.screen_y
		drawable_area = {"x": range(o_mh, P.screen_x - o_mh), "y": range(o_mv, P.screen_y - o_mv)}

		self.quad_ranges = [
			[(o_mh, s_c[1] + i_mv), (s_c[0] - i_mh, s_y - o_mv)],
			[(o_mh, o_mv), (s_c[0] - i_mh, s_c[1] - i_mv)],
			[(s_c[0] + i_mh, o_mv), (s_x - o_mh, s_c[1] - i_mv)],
			[(s_c[0] + i_mh, s_c[1] + i_mv), (s_x - o_mh, s_y - o_mv)]]
		if P.generate_quadrant_intersections:
			self.points[0][0] = (s_c[0], randrange(s_c[1] + i_mv, s_y - o_mv))
			self.points[1][0] = (randrange(o_mh, s_c[0] - i_mh), s_c[1])
			self.points[2][0] = (s_c[0], randrange(o_mv, s_c[1] - i_mv))
			self.points[3][0] = (randrange(s_c[0] + i_mh, s_x - o_mh), s_c[1])

	def __gen_real_points__(self, overwrite_intersections=False):
		start_index = 0 if overwrite_intersections else 1
		for i in range(0, 4):
			for j in range(start_index, len(self.points[i])):
				x = randrange(self.quad_ranges[i][0][0], self.quad_ranges[i][1][0])
				y = randrange(self.quad_ranges[i][0][1], self.quad_ranges[i][1][1])
				self.points[i][j] = (x, y)
		self.points = list(chain(*self.points))
		self.seg_count = len(self.points)

	def __gen_segments__(self):
		# first generate the segments to establish a path length
		first_pass_segs = []  # ie. raw interpolation unadjusted for velocity
		self.p_len = 0
		seg_type_dist = int((1.0 - P.angularity) * 10) * [True] + int(P.angularity * 10) * [False]
		segment_types = [choice(seg_type_dist)] * len(self.points)

		i = 0
		i_linear_fail = False
		i_curved_fail = False
		start = time.time()
		while len(segment_types):
			s = segment_types.pop()
			if P.verbose_mode and self.allow_verbosity:
				print "Starting segment {0} of {2} ({1})".format(i, "curve" if s else "line", len(self.points))
			p1 = self.points[i]
			try:
				p2 = self.points[i + 1]
			except IndexError:
				p2 = self.points[0]

			try:
				if not s:  # ie. not curve
					try:
						prev_seg = first_pass_segs[-1]
					except IndexError:
						prev_seg = None
					seg_ok = False
					while not seg_ok:
						if time.time() - start > P.generation_timeout:
							raise RuntimeError("Figure generation timed out.")
						if P.verbose_mode and self.allow_verbosity: print "{0} of {1}".format(i + 1, len(self.points))
						ui_request()
						segment = self.__generate_linear_segment__(p1, p2, prev_seg)
						if all(type(n) is int for n in segment):
							if not len(segment_types):
								raise TrialException("Can't change origin location.")
							p2 = segment
						else:
							seg_ok = True
					self.p_len += segment[0]
					first_pass_segs.append(segment[1])
				else:
					segment = self.__generate_curved_segment__(p1, p2, start)
					self.p_len += segment[0]
					first_pass_segs.append(segment[1])
				i += 1
				i_curved_fail = False
				i_linear_fail = False
				if P.verbose_mode and self.allow_verbosity:
					print "Segment {0} done ({1})".format(i, "curve" if s else "line")
			except TrialException:
				e = "Generation failed on {0} segment.".format("curved" if s else "linear")
				print e
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

	def segments_to_frames(self):
		# use path length and animation duration to establish a velocity and then do a second interpolation
		for i in range(0, 2):
			self.segments = []
			velocity = self.p_len / self.animate_target_time if i else 5
			for segment in self.raw_segments:
				circle = segment[0]
				try:
					p1, p2, ctrl = segment[1]
				except ValueError:
					p1, p2 = segment[1]
				if circle:
					self.segments.append(bezier_interpolation(p1, p2, ctrl, None, velocity))
				else:
					self.segments.append(linear_interpolation(p1, p2, velocity))
			if i:
				self.frames = list(chain(*self.segments))
			else:
				self.extended_interpolation = list(chain(*self.segments))

	def __generate_linear_segment__(self, p1, p2, prev_seg=None):
		if prev_seg and prev_seg[0]:
			p_prev = prev_seg[1][0]
			#  if the angle is too acute, try to shift p2 a way from prev_seg until it's ok
			seg_angle = acute_angle(p1, p_prev, p2)
			if seg_angle < self.min_lin_ang_width:
				print seg_angle, self.min_lin_ang_width, p1, p_prev, p2
				p2 = list(p2)
				# p2[0] += 1 if p_prev[0] - p2[0] > 0 else -1
				# p2[1] += 1 if p_prev[1] - p2[1] > 0 else -1

				a_p1_prev = angle_between(p1, p_prev)
				a_prev_p2 = angle_between(p_prev, p2, a_p1_prev)
				len_prev_p2 = line_segment_len(p_prev, p2)
				p2 = point_pos(p_prev, len_prev_p2 + 1, a_prev_p2, a_p1_prev)
				if p2[0] < 0 or p2[0] > P.screen_x or p2[1] < 0 or p2[1] > P.screen_y:
					raise TrialException("No appropriate angle can be generated.")
				else:
					return p2
		return [line_segment_len(p1, p2), [False, (p1, p2)]]

	def __generate_curved_segment__(self, p1, p2, start):
		# single letters here mean: r = rotation, c = control, p = point, q = quadrant, a = angle, v = vector
		report = False
		segment = None

		#  reference p is the closer of p1, p2 to the screen center for the purposes of determining direction and angle
		p_ref = p1
		if line_segment_len(p1, P.screen_x_y) > line_segment_len(p2, P.screen_x_y):
			p_ref = p2

		# gets the radial rotation between p1 and p2
		r = angle_between(p_ref, p2 if p_ref == p1 else p1)

		#  depending on the qudrant, p1->p2
		q = self.__quadrant_from_point__(p1)
		if len(q) > 1:  # if p1 is directly on an axis line an ambiguous answer is returned; check p2 instead
			q = self.__quadrant_from_point__([p2])

		# decides the radial direction from p1->p2, clockwise or counterclockwise, from which the curve will extend
		c_spin = choice([True, False])
		if report: print "p_ref: {0}\nr: {1}\nq: {2}\n c_spin: {3}".format(p_ref, r, q, c_spin)

		#  find linear distance between p1 and p2
		d_p1p2 = line_segment_len(p1, p2)
		if report: print "seg_line_len: {0}\nasym_max: {1}\nasym_min: {2}".format(d_p1p2, self.asym_max, self.asym_min)

		#  next lines decide location of the perpendicular extension from control point and p1->p2
		c_base_shift = choice(self.peak_shift_range) * d_p1p2
		c_base_amp = c_base_shift if choice(
			[1, 0]) else d_p1p2 - c_base_shift  # ensure shift not always away from p_ref
		p_c_base = point_pos(p_ref, c_base_amp, r)
		if report: print "c_base_amp: {0}\np_c_base: {1}".format(c_base_amp, p_c_base)

		#  the closer of p1, p2 to p_c_base will be p_c_ref when determining p_c_min
		if c_base_amp > 0.5 * d_p1p2:
			p_c_ref = p2 if p_ref == p1 else p1
		else:
			p_c_ref = p2 if p_ref == p2 else p1

		# choose an angle, deviating from 90 (+/-) by some random value, for p_c_ref -> p_c_base -> p_c
		try:
			sheer = choice(self.c_sheer_range)
		except IndexError:
			sheer = 0
		a_c = 90 + sheer if choice([0, 1]) else 90 - sheer

		if report: print "P.curve_sheer: {3}, c_angle_max: {0}\nc_angle_min: {1}\nc_angle: {2}".format(self.a_c_min,
																									   self.a_c_max,
																									   a_c,
																									   P.curve_sheer)
		#  get the range of x,y values for p_c
		v_c_base = [p_c_base, a_c, r, c_spin]  # ie. p_c_base as origin
		v_c_min = [p_c_ref, self.curve_min_slope, r, not c_spin]  # ie. p_c_ref as origin
		v_c_max = [p_c_ref, self.curve_max_slope, r, not c_spin]  # ie. p_c_ref as origin
		p_c_min = linear_intersection(v_c_min, v_c_base)
		p_c_max = linear_intersection(v_c_max, v_c_base)
		if report:  print "v_c_min: {0}\nv_c_maz: {1}\np_c_min: {2}\np_c_max: {3}".format(v_c_min, v_c_max, p_c_min,
																						  p_c_max)

		#  choose an initial p_c; depending on quadrant, no guarantee x,y values in p_c_min are less than p_c_max
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

		v_c_b_len = line_segment_len(p_c_ref, p_c)
		initial_v_c_b_len = v_c_b_len
		flipped_spin = False
		while not segment:
			if time.time() - start > P.generation_timeout:
				raise RuntimeError("Figure generation timed out.")
			if not p_c:
				v_c_b_len -= 1
				if v_c_b_len == 0:
					if flipped_spin:
						e = "Curve failed, p1:{0}, p2: {1}, p_c: {2}, v_c_b_len: {3}".format(p1, p2, p_c, v_c_b_len)
						print e
						raise TrialException(e)
					else:
						flipped_spin = True
						v_c_b_len = initial_v_c_b_len
				p_c = point_pos(p_c_base, v_c_b_len, a_c, r, c_spin)
			interpolation = bezier_interpolation(p1, p2, p_c)
			if interpolation is False:
				p_c = None
			else:
				return [interpolation[0], [True, [p1, p2, p_c]]]

	def __quadrant_from_point__(self, point):
		if len(point) == 1: point = point[0]
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

	def __import_figure__(self, path, join_parent=True):
		fig_archive = zipfile.ZipFile(path + ".zip")
		figure = path.split("/")[-1]
		# have no earthly clue why some times the first line works and sometimes it's the other...
		if join_parent:
			fig_file = os.path.join(figure, figure + ".tlf")
		else:
			fig_file = figure + ".tlf"
		try:
			for l in fig_archive.open(fig_file).readlines():
				attr = l.split(" = ")
				if len(attr):
					setattr(self, attr[0], eval(attr[1]))
		except KeyError:
			return self.__import_figure__(path, False)

	def render(self, np=True, trace=None, extended=False):
		surf = aggdraw.Draw("RGBA", P.screen_x_y, (0, 0, 0, 255))
		frames = self.frames if not extended else self.extended_interpolation
		p_str = "M{0} {1}".format(*frames[0])
		for s in chunk(frames, 2):
			try:
				p_str += " L{0} {1} {2} {3}".format(s[0][0], s[0][1], s[1][0], s[1][1])
			except IndexError:
				pass
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0, 0), sym, aggdraw.Pen(P.stimulus_feedback_color, 1, 255))
		# if tracing data is passed, do this all again on the same surface
		if trace:
			p_str = "M{0} {1}".format(trace[0][0], trace[0][1])
			for s in chunk(trace, 2):
				try:
					p_str += " L{0} {1} {2} {3}".format(s[0][0], s[0][1], s[1][0], s[1][1])
				except IndexError:
					pass
			sym = aggdraw.Symbol(p_str)
			surf.symbol((0, 0), sym, aggdraw.Pen(P.response_feedback_color, 1, 255))

		self.rendered = aggdraw_to_array(surf) if np else Image.frombytes(surf.mode, surf.size, surf.tostring())
		return self.rendered

	def draw(self, dots=True, flip=True):
		fill()
		blit(self.render(), flip_x=P.flip_x)
		message("Path Length: {0}".format(interpolated_path_len(self.frames), "default", location=(25, 50)))
		if dots:
			for p in self.points:
				blit(self.r_dot, 5, p, flip_x=P.flip_x)
				message(str(p[0]), "tiny", location=p)
		if flip:
			flip()

	def prepare_animation(self):
		if self.animate_target_time is None:
			self.animate_target_time = self.exp.animate_time
		self.path_length = interpolated_path_len(self.frames)
		draw_in = self.animate_target_time * 0.001
		rate = 0.016666666666667
		max_frames = int(draw_in / rate)
		delta_d = math.floor(self.path_length / max_frames)
		self.a_frames = [list(self.frames[0])]
		seg_len = 0
		for i in range(0, len(self.frames)):
			p1 = [float(p) for p in self.frames[i]]
			try:
				p2 = [float(p) for p in self.frames[i + 1]]
			except IndexError:
				p2 = [float(p) for p in self.frames[0]]
			seg_len += line_segment_len(p1, p2)
			if seg_len >= delta_d:
				self.a_frames.append(list(self.frames[i]))
				seg_len = 0

	def animate(self, practice=False):
		updated_a_frames = []
		if not P.capture_figures_mode and not practice:
			start = self.evm.trial_time

		for f in self.a_frames:
			# if P.flip_x:
			# 	f[0] = P.screen_x - f[0]
			ui_request()
			fill()
			if P.demo_mode:
				blit(self.rendered, 5, P.screen_c, flip_x=P.flip_x)
			blit(self.exp.tracker_dot, 5, f, flip_x=P.flip_x)
			flip()
			f = list(f)
			if not P.capture_figures_mode and not practice:
				updated_a_frames.append((f[0], f[1], self.evm.trial_time - start))
		if not P.capture_figures_mode and not practice:
			self.a_frames = updated_a_frames
			self.animate_time = self.evm.trial_time

			self.avg_velocity = self.path_length / self.animate_time

	def write_out(self, file_name=None, trial_data=None):
		writing_tracing = file_name is not None
		if not file_name:
			file_name = self.file_name
		if not trial_data:
			trial_data = self.a_frames

		thumb_file_name = file_name[:-4] + "_preview.png"
		thumbx_file_name = file_name[:-4] + "_ext_preview.png"
		points_file_name = file_name[:-4] + ".tlfp"
		ext_interp_file_name = file_name[:-4] + ".tlfx"
		segments_file_name = file_name[:-4] + ".tlfs"
		fig_path = os.path.join(self.exp.fig_dir, file_name)
		points_path = os.path.join(self.exp.fig_dir, points_file_name)
		segments_path = os.path.join(self.exp.fig_dir, segments_file_name)
		ext_interpolation_path = os.path.join(self.exp.fig_dir, ext_interp_file_name)
		thumb_path = os.path.join(self.exp.fig_dir, thumb_file_name)
		thumbx_path = os.path.join(self.exp.fig_dir, thumb_file_name)
		with zipfile.ZipFile(fig_path[:-3] + "zip", "a", zipfile.ZIP_DEFLATED) as fig_zip:
			f = open(fig_path, "w+")
			if P.capture_figures_mode:
				for k, v in self.__dict__.iteritems():
					if k in ["dot", "r_dot", "exp", 'rendered']:
						continue
					f.write("{0} = {1}\n".format(k, v))
			else:
				f.write(str(trial_data))
			f.close()

			if P.gen_tlfx and not writing_tracing:
				f = open(ext_interpolation_path, "w+")
				f.write(str(self.extended_interpolation))
				f.close()
				fig_zip.write(ext_interpolation_path, ext_interp_file_name)
				os.remove(ext_interpolation_path)

			if P.gen_tlfp and not writing_tracing:
				f = open(points_path, "w+")
				f.write(str(self.points))
				f.close()
				fig_zip.write(points_path, points_file_name)
				os.remove(points_path)

			if P.gen_tlfs and not writing_tracing:
				f = open(segments_path, "w+")
				f.write(",".join(str(s[1]) for s in self.raw_segments))
				f.close()
				fig_zip.write(segments_path, segments_file_name)
				os.remove(segments_path)

			if P.gen_png and not writing_tracing:
				png.from_array(self.render(), 'RGBA').save(thumb_path)
				fig_zip.write(thumb_path, thumb_file_name)
				os.remove(thumb_path)

			if P.gen_ext_png:
				png.from_array(self.render(extended=True), 'RGBA').save(thumb_path)
				fig_zip.write(thumbx_path, thumbx_file_name)
				os.remove(thumb_path)

			fig_zip.write(fig_path, file_name)
			os.remove(fig_path)

	@property
	def file_name(self):
		f_name_data = [P.participant_id, P.block_number, P.trial_number, now(True, "%Y-%m-%d"), self.exp.session_number]
		return "p{0}_s{4}_b{1}_t{2}_{3}.tlf".format(*f_name_data)
