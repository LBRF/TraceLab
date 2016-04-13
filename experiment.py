import klibs

__author__ = "Jonathan Mulle"

import time
import random
import numpy as np
from random import choice
from PIL import ImageDraw, Image
from PIL import ImagePath
from klibs import Params
from klibs.KLDraw import *
from klibs import Params
from klibs.KLDraw import *
from klibs.KLKeyMap import KeyMap
from klibs.KLDraw import colors
from klibs.KLUtilities import *
from klibs.KLConstants import *
from klibs.KLEventInterface import EventTicket as ET


WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255,0,0,255)
GREEN = (0,255,0,255)

def from_range(lower, upper, step=1):
	return random.choice(range(lower, upper, step))

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

	instructions_1 = None
	instructions_2 = None

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
		self.text_manager.add_style('instructions', 32, [2550, 255, 255, 255])
		self.canvas = Rectangle(self.canvas_size, fill=self.canvas_color, stroke=[2, self.canvas_border, STROKE_INNER])
		self.origin_proto = Ellipse(self.origin_size)
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
		self.instructions_1 = "On each trial you will have {0} seconds to study a random figure that you will later be asked to draw.\nPress any key to begin.".format(self.sample_exposure_time // 1000)
		self.instructions_2 = "Now draw the figure you have just seen.\n - Start by placing the cursor on the red dot. \n - End by placing the cursor on the green dot. \n\nPress any key to proceed."


	def block(self, block_num):
		self.fill()
		self.message(self.instructions_1, 'instructions', registration=5, location=Params.screen_c, flip=True)
		self.any_key()

	def setup_response_collector(self, trial_factors):
		self.rc.uses(RC_DRAW)
		cb_xy1 = Params.screen_c[0] - self.canvas_size // 2
		cb_xy2 = Params.screen_c[0] + self.canvas_size // 2
		self.rc.end_collection_event = 'response_period_end'
		self.rc.draw_listener.add_boundaries([('start', self.origin_boundary, EL_CIRCLE_BOUNDARY),
											  ('stop', self.origin_boundary, EL_CIRCLE_BOUNDARY),
											  ('canvas', [(cb_xy1, cb_xy1), (cb_xy2, cb_xy2)], EL_RECT_BOUNDARY)])
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

	def trial_prep(self, trial_factors):
		self.fill()
		self.figure, self.figure_segments, self.figure_dots = self.generate_figure()
		Params.clock.register_events([ET('end_exposure', self.sample_exposure_time)])
		self.show_figure()

	def trial(self, trial_factors):
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
		print self.figure_segments
		return {
			"block_num": Params.block_number,
			"trial_num": Params.trial_number,
			"figure": self.figure_segments,
			"drawing": self.rc.draw_listener.responses[0][0],
			"rt": self.rc.draw_listener.responses[0][1]
		}

	def trial_clean_up(self, trial_id, trial_factors):
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
		self.fill()
		self.blit(self.figure, 5, Params.screen_c)
		if Params.development_mode:
			for p in self.figure_dots:
				self.blit(p[0], 5, p[1])
		self.flip()

	def generate_segment_positions(self, seg_count, x_offset, y_offset, avg_dist, dist_variance):
		min_pt_dist = avg_dist - dist_variance
		max_pt_dist = avg_dist + dist_variance
		q_pts_x = []
		q_pts_y = []

		while not len(q_pts_x) == seg_count:
			x = from_range(x_offset, x_offset + 400)
			try:
				if not (x in range(q_pts_x[-1] - min_pt_dist, q_pts_x[-1] + min_pt_dist)):
					q_pts_x.append(x)
			except IndexError:
				q_pts_x.append(x)
		while not len(q_pts_y) == seg_count:
			y = from_range(y_offset, y_offset + 400)
			try:
				if not (y in range(q_pts_y[-1] - min_pt_dist, q_pts_y[-1] + min_pt_dist)):
					q_pts_y.append(y)
			except IndexError:
				q_pts_y.append(y)
		q_points = []
		for p in q_pts_x:
			q_points.append((p, q_pts_y[q_pts_x.index(p)]))
		return q_points

	def generate_arc_controls(self, dest, origin, quadrant):
		m = midpoint(dest, origin)
		rotation = int(angle_between(dest, origin))
		angle_1 =  int(np.random.normal(90, 10)) + rotation
		angle_2 =  int(np.random.normal(90, 10)) + rotation
		quad_offset = 0
		if quadrant == 0:
			quad_offset = 180
		if quadrant == 1:
			quad_offset = 90
		if quadrant == 3:
			quad_offset += 270
		angle_1 += quad_offset
		angle_2 += quad_offset
		mp_len = int(line_segment_len(dest, m))
		amplitude_1 = from_range(mp_len // 2, mp_len)
		amplitude_2 = from_range(mp_len // 2, mp_len)
		c1 = point_pos(dest[0], dest[1], amplitude_1, angle_1)
		c2 = point_pos(origin[0], origin[1], amplitude_2, angle_2)
		if any(i for i in c1 + c2) < 0:
			return self.generate_arc_controls(dest, origin, quadrant)
		d_dest_c1 = line_segment_len(dest, c1)
		d_dest_c2 = line_segment_len(dest, c2)
		return [c1, c2] if d_dest_c1 > d_dest_c2 else [c2, c1]

	def generate_figure(self):
		BOT_L = 0
		TOP_L = 1
		TOP_R = 2
		BOT_R = 3
		initial = (400, from_range(450, 750))
		segments = []
		# surf = FreeDraw(800, 800, [1, RED, STROKE_INNER], initial)
		# segments.append([KLD_MOVE,initial])
		min_segments_per_q = 2
		max_segments_per_q = 4
		q_intersects = [(from_range(50, 350), 400), (400, from_range(50, 350)), (from_range(450, 750), 400), initial]
		avg_dist = 150
		dist_variance = 50
		for quad in range(0,4):
			seg_count = from_range(min_segments_per_q, max_segments_per_q)
			x_offset = 0 if quad in [BOT_L, TOP_L] else 400
			y_offset = 0 if quad in [TOP_L, TOP_R] else 400
			origin = None
			for j in range(0, seg_count):
				# generate start and end points for each segment in the quadrant
				q_points = self.generate_segment_positions(seg_count, x_offset, y_offset, avg_dist, dist_variance)

				# set origin to the destination of previous segment
				o = initial if origin is None else origin

				# assign destination point; quadrant intersect for last segment of each quadrant
				d = q_points[j] if j < seg_count - 1 else q_intersects[quad]

				# choose a segment type
				s = random.choice([KLD_ARC, KLD_LINE])
				# surf.move(o)
				if s == KLD_LINE:
					# surf.line(d, o)
					segments.append([KLD_LINE, [d, o]])
				if s == KLD_ARC:
					c = self.generate_arc_controls(d, o, quad)
					# surf.arc(d, c, o)
					segments.append([KLD_ARC, [c[0], c[1], d]])
				origin = d

		self.fill()
		surf = aggdraw.Draw("RGBA", (800, 800), (255,255,255,255))
		p_str = "M{0} {1}".format(*initial)
		for s in segments:
			if s[0] == KLD_LINE:
				p_str += " L{0} {1}".format(*s[1][0])
			if s[0] ==  KLD_ARC:
				# pts = s[1][0] + s[1][1] + s[1][2]
				pts = s[1][0] + s[1][2]
				# p_str += " Q {0} {1} {2} {3} {4} {5}".format(*pts)
				p_str += " Q {0} {1} {2} {3}".format(*pts)
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0,0), sym, aggdraw.Pen((255,0,0), 1, 255))
		# self.blit(surf.draw(True).render())
		dot_fill = [0,0,205]
		increment = 25
		dots = []
		for seq in segments:
			diff = 0
			if dot_fill[2] + increment <= 255:
				dot_fill[2] += increment
			if dot_fill[2] + increment > 255:
				diff = increment - (255 - dot_fill[2])
				dot_fill[2] = 255
			if dot_fill[1] + increment <= 255:
				dot_fill[1] += increment
			if dot_fill[1] + diff > 255:
				diff =- (255 - dot_fill[1])
				dot_fill[1] = 255
			if diff > 0:
				dot_fill[0] += diff
				if dot_fill[0] > 200:
					dot_fill[0] = 200
			if seq[0] in [KLD_LINE, KLD_MOVE]:
				p = list(seq[1][0])
			if seq[0] == KLD_ARC:
				p = list(seq[1][-1])
			p[0] += Params.screen_x // 2 - 400
			p[1] += Params.screen_y // 2 - 400
			dots.append([Ellipse(5, fill=dot_fill), p])
		return [aggdraw_to_array(surf), p_str,  dots]




	def generate_segment_positions(seg_count, x_offset, y_offset, avg_dist, dist_variance):
		min_pt_dist = avg_dist - dist_variance
		max_pt_dist = avg_dist + dist_variance
		q_pts_x = []
		q_pts_y = []

		while not len(q_pts_x) == seg_count:
			x = from_range(x_offset, x_offset + 400)
			try:
				if not (x in range(q_pts_x[-1] - min_pt_dist, q_pts_x[-1] + min_pt_dist)):
					q_pts_x.append(x)
			except IndexError:
				q_pts_x.append(x)
		while not len(q_pts_y) == seg_count:
			y = from_range(y_offset, y_offset + 400)
			try:
				if not (y in range(q_pts_y[-1] - min_pt_dist, q_pts_y[-1] + min_pt_dist)):
					q_pts_y.append(y)
			except IndexError:
				q_pts_y.append(y)
		q_points = []
		for p in q_pts_x:
			q_points.append((p, q_pts_y[q_pts_x.index(p)]))
		return q_points

	def generate_arc_controls(self, dest, origin, quadrant):
		m = midpoint(dest, origin)
		rotation = int(angle_between(dest, origin))
		angle_1 =  int(np.random.normal(90, 10)) + rotation
		angle_2 =  int(np.random.normal(90, 10)) + rotation
		quad_offset = 0
		if quadrant == 0:
			quad_offset = 180
		if quadrant == 1:
			quad_offset = 90
		if quadrant == 3:
			quad_offset += 270
		angle_1 += quad_offset
		angle_2 += quad_offset
		mp_len = int(line_segment_len(dest, m))
		amplitude_1 = from_range(mp_len // 2, mp_len)
		amplitude_2 = from_range(mp_len // 2, mp_len)
		c1 = point_pos(dest[0], dest[1], amplitude_1, angle_1)
		c2 = point_pos(origin[0], origin[1], amplitude_2, angle_2)
		if any(i for i in c1 + c2) < 0:
			return self.generate_arc_controls(dest, origin, quadrant)
		d_dest_c1 = line_segment_len(dest, c1)
		d_dest_c2 = line_segment_len(dest, c2)
		return [c1, c2] if d_dest_c1 > d_dest_c2 else [c2, c1]

	def generate_figure(self):
		BOT_L = 0
		TOP_L = 1
		TOP_R = 2
		initial_position = (400, from_range(450, 750))
		segments = []
		# surf = FreeDraw(800, 800, [1, RED, STROKE_INNER], initial)
		# segments.append([KLD_MOVE,initial])
		min_segments_per_q = 2
		max_segments_per_q = 4
		quadrant_intersects = [(random.choice(range(50, 350)), 400),
						(400, random.choice(range(50, 350))),
						(random.choice(range(450, 750)), 400), initial_position]
		avg_dist = 150		# used to give some control
		dist_variance = 50	# over the points I later join
		for quad in range(0,4):
			seg_count = from_range(min_segments_per_q, max_segments_per_q)
			x_offset = 0 if quad in [BOT_L, TOP_L] else 400
			y_offset = 0 if quad in [TOP_L, TOP_R] else 400
			origin = None
			for j in range(0, seg_count):
				# generate start and end points for each segment in the quadrant
				q_points = self.generate_segment_positions(seg_count, x_offset, y_offset, avg_dist, dist_variance)

				# set origin to the destination of previous segment
				o = initial_position if origin is None else origin

				# assign destination point; quadrant intersect for last segment of each quadrant
				d = q_points[j] if j < seg_count - 1 else quadrant_intersects[quad]

				# choose a segment type
				s = random.choice([KLD_ARC, KLD_LINE])
				# surf.move(o)
				if s == KLD_LINE:
					# surf.line(d, o)
					segments.append([KLD_LINE, [d, o]])
				if s == KLD_ARC:
					c = self.generate_arc_controls(d, o, quad)
					# surf.arc(d, c, o)
					segments.append([KLD_ARC, [c[0], c[1], d]])
				origin = d

		surf = aggdraw.Draw("RGBA", (800, 800), (255,255,255,255))
		p_str = "M{0} {1}".format(*initial_position)
		for s in segments:
			if s[0] == KLD_LINE:
				p_str += " L{0} {1}".format(*s[1][0])
			if s[0] ==  KLD_ARC:
				pts = s[1][0] + s[1][2]
				p_str += " Q {0} {1} {2} {3}".format(*pts)
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0,0), sym, aggdraw.Pen((255,0,0), 1, 255))

		return surf