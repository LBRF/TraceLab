# -*- coding: utf-8 -*-
__author__ = 'jono'
import klibs.KLParams as Params
from klibs.KLUtilities import *
from klibs.KLDraw import Ellipse
from random import randrange, choice
from itertools import chain
from PIL import ImagePath, ImageDraw, Image
import png
import zipfile
import aggdraw
from klibs.KLNumpySurface import aggdraw_to_array

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


# def linear_interpolation(origin, destination, segmented=True):
# 	d_x = destination[0] - origin[0]
# 	d_y = destination[1] - origin[1]
# 	theta = angle_between(origin, destination)
# 	steps = abs(d_x) if abs(d_x) < abs(d_y) else abs(d_y)
# 	points = [origin]
# 	for i in range(steps):
# 		points.append(point_pos(origin, i, theta))
# 	points.append(destination)
# 	if segmented:
# 		segments = list(chunk(points, 2))
# 		return segments if len(segments[-1]) == 2 else segments[:-1]
# 	else:
# 		return points

"""
Velocity is measured in (whatever units your distance function uses)/(draw call)
dt is time between draw calls
"""
def linear_interpolation(origin, destination, velocity=5, dt=0.01666667):
	#Ensure the point travels along straight segments at the expected velocity
	angle = angle_between(origin, destination)
	distance = line_segment_len(origin, destination)
	time_to_complete = distance/velocity
	###
	steps = int(time_to_complete/dt) #abs(d_x) if abs(d_x) < abs(d_y) else abs(d_y)
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

# """
# Velocity is measured in (whatever units your distance function uses)/(draw call)
# dt is time between draw calls
# """
# def bezier_interpolation(origin, destination, control_o, control_d=None, velocity=5, dt=0.016):
# 		destination = tuple(destination)
# 		origin = tuple(origin)
# 		control_o = tuple(control_o)
# 		if control_d:
# 			control_d = tuple(control_d)
# 		points = [origin, control_o, control_d, destination] if control_d else [origin, control_o, destination]
# 		n = len(points)
#
# 		def bezier(transitions):
# 			combinations = pascal_row(n - 1)
# 			result = []
# 			for t in transitions:
# 				t_powers = (t ** i for i in range(n))
# 				u_powers = reversed([(1 - t) ** i for i in range(n)])
# 				coefficients = [c * a * b for c, a, b in zip(combinations, t_powers, u_powers)]
# 				result.append(list(sum([coef * p for coef, p in zip(coefficients, ps)]) for ps in zip(*points)))
# 			return result
#
# 		# Estimate the length of the curve
# 		first_guess = bezier([0.01 * t for t in range(101)])
# 		length_of_first_guess = path_len(first_guess)
# 		# Calculate the time to traverse the curve at expected velocity
# 		time_to_completion = length_of_first_guess/velocity
# 		# The ceil call here biases long
# 		# If you want to resolve issues of dt not dividing time to complete
# 		# another way, feel free. The shorter the lines relative to the
# 		# velocity, the more error this introduces.
# 		steps = int(math.ceil(time_to_completion/dt))
#
# 		# The +1 ensures we get to the end
# 		final_curve = bezier([t/steps for t in range(steps+1)])
#
# 		return [ (int(p[0]), int(p[1])) for p in final_curve]
#
#


class DrawFigure(object):

	def __init__(self, exp, import_path=None):
		self.exp = exp
		self.seg_count = None
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
		self.width = Params.screen_x - (2 * Params.outer_margin_h)
		self.height = Params.screen_y - (2 * Params.outer_margin_h)
		if import_path:
			self.__import_figure(import_path)
			return
		if not Params.capture_figures_mode:
			fname_data = [Params.participant_id, Params.block_number,  Params.trial_number, now(True, "%Y-%m-%d"), Params.session_number]
			self.file_name = "p{0}_s{4}_b{1}_t{2}_{3}.tlf".format(*fname_data)
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
		self.seg_count = sum(len(i) for i in self.points)

	def __gen_segments__(self):
		for i in range(0, len(self.points)):
			curves = int((1.0 - Params.angularity) * 10) * [False]
			lines = int(Params.angularity * 10) * [True]
			if choice(curves+lines):
				try:
					self.segments.append([False, self.points[i], self.points[i+1]])
				except IndexError:
					self.segments.append([False, self.points[i], self.points[0]])
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
		bezier_path_lens = []
		bezier_densities = []
		for s in self.segments:
			if s[0] is not False:
				p_len = interpolated_path_len(s)
				bezier_path_lens.append(p_len)
				bezier_densities.append(p_len / len(s))
		avg_density = sum(bezier_densities) / len(bezier_densities)
		v = 0.001
		while v / 0.016 < avg_density:
			v+=0.1
		for i in range(0, len(self.segments)):
			if self.segments[i][0] is False:
				# print self.segments[i]
				# continue
				self.segments[i] = linear_interpolation(self.segments[i][1], self.segments[i][2], v)
				# print self.segments[i]
				# self.exp.quit()
				# try:
				# except IndexError:
				# 	self.segments[i] = linear_interpolation(self.points[i], self.points[0], v)
		self.frames = list(chain(*self.segments))

	def __import_figure(self, path):
		fig_archive = zipfile.ZipFile(path + ".zip")
		figure = path.split("/")[-1]
		fig_file = os.path.join(figure, figure + ".tlf")
		for l in fig_archive.open(fig_file).readlines():
			attr = l.split(" = ")
			if len(attr):
				setattr(self, attr[0], eval(attr[1]))

	def render(self,np=True):
		surf = aggdraw.Draw("RGBA", (self.width, self.height), Params.default_fill_color)
		p_str = "M{0} {1}".format(*self.frames[0])
		for s in chunk(self.frames, 2):
			try:
				p_str += " L{0} {1} {2} {3}".format(*(list(s[0]) + list(s[1])))
			except IndexError:
				pass
		sym = aggdraw.Symbol(p_str)
		surf.symbol((0, 0), sym, aggdraw.Pen((75, 75, 75), 1, 255))
		return aggdraw_to_array(surf) if np else Image.frombytes(surf.mode, surf.size, surf.tostring())

	def draw(self, dots=True, flip=True):
		self.exp.fill()
		self.exp.blit(self.render())
		self.exp.message("Path Length: {0}".format(interpolated_path_len(self.frames), "default", location=(25,50)))
		if dots:
			for p in self.points:
				self.exp.blit(self.r_dot, 5, p)
				self.exp.message(str(p[0]), "tiny", location=p)
		if flip:
			self.exp.flip()


	def animate(self, duration):
		self.path_len = interpolated_path_len(self.frames)
		surface = self.render()
		draw_in = duration * 0.001
		rate = 0.01666666667
		max_frames = int(draw_in / rate)
		delta_d = math.floor(self.path_len / max_frames)
		a_frames = [self.frames[0]]
		seg_len = 0
		mouse = []
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
				a_frames.append((self.frames[i][0] + Params.outer_margin_h, self.frames[i][1] + Params.outer_margin_v))
				seg_len = 0

		#
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
			self.exp.ui_request()
			if Params.trace_mode:
				mouse.append(mouse_pos())
			# while time.time() < rate + last_f:
			# 	pump()
			# f += 1
			# pos = a_frames[f]
			self.exp.fill()
			# self.exp.blit(surface, 5, Params.screen_c)
			self.exp.blit(self.exp.tracker_dot, 5, f)
			self.exp.flip()
			f = list(f)
			try:
				f.append(Params.clock.trial_time)
			except RuntimeError:
				pass  # for capture mode
			last_f = time.time()

	def write_out(self, file_name=None, drawing_data=None):
		if not file_name:
			file_name = self.file_name
		thumb_file_name = file_name[:-4] + "_preview.png"
		fig_path = os.path.join(self.exp.fig_dir, file_name)
		thumb_path = os.path.join(self.exp.fig_dir, thumb_file_name)
		with zipfile.ZipFile(fig_path[:-3] + "zip", "a", zipfile.ZIP_DEFLATED) as fig_zip:
			f = open(fig_path, "w+")
			if Params.capture_figures_mode:
				for k, v in self.__dict__.iteritems():
					if k in ["dot", "r_dot", "exp"]:
						continue
					f.write("{0} = {1}\n".format(k, v))
			elif drawing_data:
				f.write(str(drawing_data))
			else:
				f.write("frames = " + str(self.frames))
			f.close()
			if not drawing_data:
				png.from_array(self.render(), 'RGBA').save(thumb_path)
				fig_zip.write(thumb_path, thumb_file_name)
				os.remove(thumb_path)
			fig_zip.write(fig_path, file_name)
			os.remove(fig_path)
