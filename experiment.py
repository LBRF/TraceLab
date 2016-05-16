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
    if n&1 == 0:
        # n is even
        result.extend(reversed(result[:-1]))
    else:
        result.extend(reversed(result))
    return result


def bezier_interpolation(origin, destination, control_o, control_d=None, segmented=True, integers=True):
		destination = tuple(destination)
		origin = tuple(origin)
		control_o = tuple(origin)
		if control_d:
			control_d = tuple(control_d)
		points = [origin, control_o, control_d, destination] if control_d else [origin, control_o, destination]
		n = len(points)
		combinations = pascal_row(n - 1)

		def bezier(transitions):
			result = []
			for t in transitions:
				t_powers = (t ** i for i in range(n))
				u_powers = reversed([(1 - t) ** i for i in range(n)])
				coefficients = [c * a * b for c, a, b in zip(combinations, t_powers, u_powers)]
				result.append(list(sum([coef * p for coef, p in zip(coefficients, ps)]) for ps in zip(*points)))
			return result

		break_next = False
		segments = []
		points = []
		print bezier([0.01 * t for t in range(101)])
		for pos in chunk(bezier([0.01 * t for t in range(101)]), 2):
			try:
				if integers:
					pos[0] = tuple(int(i) for i in pos[0])
					pos[1] = tuple(int(i) for i in pos[1])
				if break_next:
					segments.append([break_next, destination])
					points.append(break_next)
					points.append(destination)
					break
				if pos[0] == destination:
					break_next = pos[0]
					continue
				if len(pos[0]) == 2 and len(pos[1]) == 2:
					segments.append(pos)
					points.append(pos[0])
					points.append(pos[1])
			except IndexError:
				break
		if segmented:
			return segments if len(segments[-1]) == 2 else segments[:-1]
		else:
			return points

print bezier_interpolation((0,0), (100,00), (50,0), segmented=False)
exit()

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
	tracker_dot_size = 5
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
		self.text_manager.add_style('instructions', 32, [255, 255, 255, 255])
		self.text_manager.add_style('tiny', 12, [255, 255,255, 255])
		self.figure = DrawFigure(self)
		self.quit()
		self.canvas = Rectangle(self.canvas_size, fill=self.canvas_color, stroke=[2, self.canvas_border, STROKE_INNER])
		self.origin_proto = Ellipse(self.origin_size)
		self.tracker_dot_proto = Ellipse(self.tracker_dot_size)
		self.tracker_dot_proto.fill = [255, 0, 0]
		self.tracker_dot = self.tracker_dot_proto.render()
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
		self.segment_compilation = None
		self.__generate_null_points__()
		self.__gen_quad_intersects__()
		self.__gen_real_points__()
		self.__gen_segments__()
		for s in self.segments:
			print s
		self.draw()

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
		o_m = Params.outer_margin
		s_c = Params.screen_c
		s_x = Params.screen_x
		s_y = Params.screen_y
		self.quad_ranges = [
			[(0, s_c[1]), (s_c[0], s_y)],
			[(0,0), s_c],
			[(s_c[0], 0), (s_x, s_c[1])],
			[s_c, Params.screen_x_y]]
		self.points[0][0] = (s_c[0], randrange(s_c[1] + i_m, s_y - o_m))
		self.points[1][0] = (randrange(o_m, s_c[0] - i_m), s_c[1])
		self.points[2][0] = (s_c[0], randrange(o_m, s_c[1] - i_m))
		self.points[3][0] = (randrange(s_c[0] + i_m, s_x - o_m), s_c[1])


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
			if choice(curves+lines) and False:
				try:
					self.segments.append(linear_interpolation(self.points[i], self.points[i + 1], segmented=False))
				except IndexError:
					self.segments.append(linear_interpolation(self.points[i], self.points[0], segmented=False))
			else:
				try:
					amp = line_segment_len(self.points[i], self.points[i + 1])
					c = point_pos(midpoint(self.points[i], self.points[i + 1]), amp, 90)
					self.segments.append(bezier_interpolation(self.points[i], self.points[i + 1], c, segmented=False))
				except IndexError:
					amp = line_segment_len(self.points[i], self.points[0])
					c = point_pos(midpoint(self.points[i], self.points[0]), amp, 90)
					self.segments.append(bezier_interpolation(self.points[i], self.points[0], c, segmented=False))

		print self.segments
		self.segment_compilation = list(chain(*self.segments))
		print self.segment_compilation

	def render(self):
		surf = aggdraw.Draw("RGBA", Params.screen_x_y, Params.default_fill_color)
		p_str = "M{0} {1}".format(*self.segment_compilation[0])
		for s in chunk(self.segment_compilation, 2):
			try:
				p_str += " L{0} {1} {2} {3}".format(*(list(s[0]) + list(s[1])))
			except IndexError:
				pass
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0, 0), sym, aggdraw.Pen((255, 0, 0), 1, 255))
		return aggdraw_to_array(surf)

	def draw(self):
		self.exp.fill()
		self.exp.blit(self.render())
		for p in self.points:
			self.exp.blit(self.r_dot, 5, p)
			self.exp.message(str(p[0]), "tiny", location=p)
		self.exp.flip()
		self.exp.any_key()





	# 1. generate segments based on quadrant density
	# 2. distribute path length amongst segments
	# 3. decide nature of segment (curve/line)
	# 4. determine curve characteristics
	# 5. interpolate

	# def generate_segment_positions(self, seg_count, x_offset, y_offset, avg_dist, dist_variance):
	# 	min_pt_dist = avg_dist - dist_variance
	# 	max_pt_dist = avg_dist + dist_variance
	# 	q_pts_x = []
	# 	q_pts_y = []
	#
	# 	while not len(q_pts_x) == seg_count:
	# 		x = from_range(x_offset, x_offset + 400)
	# 		try:
	# 			if not (x in range(q_pts_x[-1] - min_pt_dist, q_pts_x[-1] + min_pt_dist)):
	# 				q_pts_x.append(x)
	# 		except IndexError:
	# 			q_pts_x.append(x)
	# 	while not len(q_pts_y) == seg_count:
	# 		y = from_range(y_offset, y_offset + 400)
	# 		try:
	# 			if not (y in range(q_pts_y[-1] - min_pt_dist, q_pts_y[-1] + min_pt_dist)):
	# 				q_pts_y.append(y)
	# 		except IndexError:
	# 			q_pts_y.append(y)
	# 	q_points = []
	# 	for p in q_pts_x:
	# 		q_points.append((p, q_pts_y[q_pts_x.index(p)]))
	# 	return q_points
	#
	# def generate_arc_controls(self, dest, origin, quadrant):
	# 	m = midpoint(dest, origin)
	# 	rotation = int(angle_between(dest, origin))
	# 	angle_1 =  int(np.random.normal(90, 10)) + rotation
	# 	angle_2 =  int(np.random.normal(90, 10)) + rotation
	# 	quad_offset = 0
	# 	if quadrant == 0:
	# 		quad_offset = 180
	# 	if quadrant == 1:
	# 		quad_offset = 90
	# 	if quadrant == 3:
	# 		quad_offset += 270
	# 	angle_1 += quad_offset
	# 	angle_2 += quad_offset
	# 	mp_len = int(line_segment_len(dest, m))
	# 	amplitude_1 = from_range(mp_len // 2, mp_len)
	# 	amplitude_2 = from_range(mp_len // 2, mp_len)
	# 	c1 = point_pos(dest, amplitude_1, angle_1)
	# 	c2 = point_pos(origin, amplitude_2, angle_2)
	# 	if any(i for i in c1 + c2) < 0:
	# 		return self.generate_arc_controls(dest, origin, quadrant)
	# 	d_dest_c1 = line_segment_len(dest, c1)
	# 	d_dest_c2 = line_segment_len(dest, c2)
	# 	return [c1, c2] if d_dest_c1 > d_dest_c2 else [c2, c1]
	#
	# def generate_figure(self):
	# 	BOT_L = 0
	# 	TOP_L = 1
	# 	TOP_R = 2
	#
	# 	initial = (400, from_range(450, 750))
	# 	segments = []
	# 	min_segments = 8
	# 	max_segments = 15
	# 	min_segments_per_q = 1
	# 	max_segments_per_q = 4
	# 	segment_count = from_range(min_segments, max_segments)
	# 	q_intersects = [(from_range(50, 350), 400), (400, from_range(50, 350)), (from_range(450, 750), 400), initial]
	# 	avg_dist = 150
	# 	dist_variance = 50
	# 	seg_count = from_range(min_segments_per_q, max_segments_per_q)
	# 	segment_count -=  seg_count
	# 	if segment_count < 0:
	# 		seg_count += segment_count
	# 	if seg_count < 1:
	# 	for quad in range(0,4):
	#
	# 		x_offset = 0 if quad in [BOT_L, TOP_L] else 400
	# 		y_offset = 0 if quad in [TOP_L, TOP_R] else 400
	# 		origin = None
	# 		for j in range(0, seg_count):
	# 			# generate start and end points for each segment in the quadrant
	# 			q_points = self.generate_segment_positions(seg_count, x_offset, y_offset, avg_dist, dist_variance)
	#
	# 			# set origin to the destination of previous segment
	# 			o = initial if origin is None else origin
	#
	# 			# assign destination point; quadrant intersect for last segment of each quadrant
	# 			d = q_points[j] if j < seg_count - 1 else q_intersects[quad]
	#
	# 			# choose a segment type
	# 			s = random.choice([KLD_ARC, KLD_LINE])
	#
	# 			if s == KLD_LINE:
	# 				seg_pts = linear_interpolation(o, d, segmented=False)
	# 			if s == KLD_ARC:
	# 				m = midpoint(o, d)
	# 				a = angle_between(o, d)
	# 				c = point_pos(m, random.choice(range(100, 200)), a + 90)
	# 				seg_pts = bezier_interpolation(o, d, c, segmented=False)
	# 			segments += seg_pts
	# 			# for i in range(len(seg_pts)):
	# 			# 	segments.append((seg_pts[i][0] + x_offset, seg_pts[i][1] + y_offset))
	#
	# 			origin = d
	#
	# 	return segments
