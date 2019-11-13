# -*- coding: utf-8 -*-
__author__ = "Austin Hurst"

import math
from klibs.KLUtilities import iterable, point_pos, clip, line_segment_len


def linear_intersection(line_1, line_2):
	"""Not sure exactly what this does, Jon wrote it. Used in curve segment generationn.
	Copy/pasted from KLUtilities so I can eventually remove it from there.
	"""
	# first establish if lines are given as absolute lengths or origins and angles
	l1_xy = None
	l2_xy = None
	try:
		if not all(iterable(p) for p in line_1 + line_2):
			# allow for rotation and clockwise arguments to be passed
			l1_xy = (line_1[0], point_pos(line_1[0], 9999999, *line_1[1:]))
			l2_xy = (line_2[0], point_pos(line_2[0], 9999999, *line_2[1:]))
	except AttributeError:
		raise ValueError("Lines must be either 2 x,y pairs or 1 x,y pair and a radial description.")
	d_x = (l1_xy[0][0] - l1_xy[1][0], l2_xy[0][0] - l2_xy[1][0])
	d_y = (l1_xy[0][1] - l1_xy[1][1], l2_xy[0][1] - l2_xy[1][1])

	def determinant(a, b):
		return a[0] * b[1] - a[1] * b[0]

	div = float(determinant(d_x, d_y))

	if not div:
		raise ValueError('Supplied lines do not intersect.')
	d = (determinant(*l1_xy[0:2]), determinant(*l2_xy[0:2]))

	return (determinant(d, d_x) / div, determinant(d, d_y) / div)


def interpolated_path_len(points):
	x, y = zip(*points)
	n = len(x)
	lv = [math.sqrt((x[i]-x[i-1])**2 + (y[i]-y[i-1])**2) for i in range(n)]
	return sum(lv)


def linear_transitions(start, end, velocity, fps=60):
	"""Generates transition points along a given line for animating at a constant velocity.
	"""

	duration = line_segment_len(start, end) / float(velocity)
	steps = int(duration / (1000.0 / fps))
	transitions = [t / float(steps - 1) for t in range(steps)]

	return transitions


def linear_transitions_by_dist(start, end, dist_per_frame, offset=0):
	"""Generates transition points along a given line for animating at a constant velocity,
	moving at a constant distance (in pixels) per frame.

	Unlike the regular linear_transitions function, this does not guarantee that the endpoint
	of the curve (transition = 1.0) is included in the returned list, opting instead to match
	the provided speed (dist_per_frame) as closely as possible. Additionally, a starting offset
	can be specified defining the distance along the curve that the first transition should be.
	"""

	dist = float(line_segment_len(start, end))
	frames = int(round((dist - offset) / float(dist_per_frame), 8))
	transitions = [(offset + f * dist_per_frame) / dist for f in range(frames + 1)]

	return transitions



def linear_interpolation(start, end, transitions):
	"""Interpolates a number of pixel coordinates along the length of a given line, based on a set
	of transition values from 0.0 (start point) to 1.0 (end point). The returned list will be the
	same length as the provided list of transition values.

	Args:
		start (tuple): The (x, y) coordinates of the line start point.
		end (tuple): The (x, y) coordinates of the line end point.
		transitions (list): A list of floats between 0.0 and 1.0 (inclusive) indicating the points
			along the line to interpolate pixel coordinates for.

	Returns:
		list: A list of (x, y) integer pixel coordinates
	"""

	x = [int(start[0] + t * (end[0] - start[0])) for t in transitions]
	y = [int(start[1] + t * (end[1] - start[1])) for t in transitions]

	return list(zip(x, y))


def bezier_length(start, ctrl, end):
	"""Calculates the length of a quadratic bezier curve defined by points 'start' (starting point),
	'ctrl' (control point), and 'end' (endpoint), using actual math intstead of line interpolation.

	Based on equation & C code from http://segfaultlabs.com/docs/quadratic-bezier-curve-length
	(link dead, but available via wayback)
	"""
	ax = start[0] - 2 * ctrl[0] + end[0]
	ay = start[1] - 2 * ctrl[1] + end[1]
	bx = 2 * ctrl[0] - 2 * start[0]
	by = 2 * ctrl[1] - 2 * start[1]

	A = 4 * (ax ** 2 + ay ** 2)
	B = 4 * (ax * bx + ay * by)
	C = bx ** 2 + by ** 2

	sqrtABC = 2 * math.sqrt(A + B + C)
	A2 = math.sqrt(A)
	A32 = 2 * A * A2
	C2 = 2 * math.sqrt(C)
	BA = B / float(A2)

	n1 = A32 * sqrtABC + A2 * B * (sqrtABC - C2)
	n2 = ((4 * C * A) - B ** 2) * math.log((2 * A2 + BA + sqrtABC) / (BA + C2))
	d = 4 * A32

	return (n1 + n2) / float(d)


def bezier_bounds(start, ctrl, end):
	"""Calculate and return the top-left and bottom-right coordinates of the
	rectangle bounding a bezier.
	"""
	ax, ay = (start[0] - ctrl[0], start[1] - ctrl[1])
	bx, by = (end[0] - ctrl[0], end[1] - ctrl[1])
	min_x, max_x = sorted([start[0], end[0]])
	min_y, max_y = sorted([start[1], end[1]])

	if not (min_x <= ctrl[0] <= max_x and min_y <= ctrl[1] <= max_y):
		# Verify that control point isn't exactly between start & end to avoid dividing by zero
		if not (2 * ctrl[0] == start[0] + end[0]):
			tx = clip((start[0] - ctrl[0]) / (start[0] - 2.0 * ctrl[0] + end[0]), 0.0, 1.0)
			x = ctrl[0] + ax * (1 - tx) ** 2 + bx * tx ** 2
			min_x, max_x = (min(min_x, x), max(max_x, x))
		if not (2 * ctrl[1] == start[1] + end[1]):
			ty = clip((start[1] - ctrl[1]) / (start[1] - 2.0 * ctrl[1] + end[1]), 0.0, 1.0)
			y = ctrl[1] + ay * (1 - ty) ** 2 + by * ty ** 2
			min_y, max_y = (min(min_y, y), max(max_y, y))

	return [(min_x, min_y), (max_x, max_y)]


def bezier_points(start, ctrl, end, points=100):
	transitions = [i / float(points) for i in range(0, points + 1)]
	ax, ay = (start[0] - ctrl[0], start[1] - ctrl[1])
	bx, by = (end[0] - ctrl[0], end[1] - ctrl[1])
	x = [ctrl[0] + ax * (1 - t) ** 2 + bx * t ** 2 for t in transitions]
	y = [ctrl[1] + ay * (1 - t) ** 2 + by * t ** 2 for t in transitions]
	return (x, y)


def bezier_distmap(start, ctrl, end, res=200):
	"""Creates a transition value to distance map for a given bezier curve, allowing for
	the generation of transitions corresponding to appromixately equidistant points along
	the curve.

	Args:
		start (tuple): The (x, y) coordinates of the bezier start point.
		end (tuple): The (x, y) coordinates of the bezier end point.
		ctrl (tuple): The (x, y) coordinates of the bezier control point.
		res (int, optional): The resolution (in number of samples) of the distance map.
			Defaults to 200 samples.
	"""

	# Create t-to-distance map for approximating constant velocity
	x, y = bezier_points(start, ctrl, end, points=res)
	dist_map = [0.0]
	total_dist = 0 # cumulative length of full curve
	for i in range(0, res - 1):
		dx = x[i + 1] - x[i]
		dy = y[i + 1] - y[i]
		total_dist += math.sqrt(dx ** 2 + dy ** 2)
		dist_map.append(total_dist)

	return dist_map


def bezier_transitions(start, ctrl, end, velocity, fps=60):
	"""Generates transition points along a given bezier curve for animating at a
	constant velocity.

	Since equidistant transition points for a bezier curve don't translate to evenly-spaced
	points along the curve, we need to approximate the correct transition point values for
	constant velocity here.
	"""
	# Create t-to-distance map for approximating constant velocity
	res = 200
	dist_map = bezier_distmap(start, ctrl, end, res)
	total_dist = dist_map[-1]

	# Determine the range of t values needed to traverse the curve in steps of
	# equal length for the given velocity
	duration = total_dist / velocity
	steps = int(round(duration / (1000.0 / fps)))
	stepsize = total_dist / steps
	transitions = []
	for s in range(steps + 1):
		seg_len = stepsize * s
		for i in range(res):
			if i == (res - 1):
				t = i
				break
			elif dist_map[i + 1] >= seg_len:
				t_diff = (seg_len - dist_map[i]) / (dist_map[i + 1] - dist_map[i])
				t = i + t_diff
				break
		transitions.append(t / float(res - 1))

	return transitions


def bezier_transitions_by_dist(start, ctrl, end, dist_per_frame, offset=0):
	"""Generates transition points along a given bezier curve for animating at a
	constant velocity, moving at a constant distance (in pixels) per frame.

	Unlike the regular bezier_transitions function, this does not guarantee that the endpoint
	of the curve (transition = 1.0) is included in the returned list, opting instead to match
	the provided speed (dist_per_frame) as closely as possible. Additionally, a starting offset
	can be specified defining the distance along the curve that the first transition should be.
	"""

	# Create t-to-distance map for approximating constant velocity
	res = 200
	dist_map = bezier_distmap(start, ctrl, end, res)

	dist = bezier_length(start, ctrl, end)
	frames = int(round((dist - offset) / float(dist_per_frame), 8))
	transitions = []
	for f in range(frames + 1):
		seg_len = offset + f * dist_per_frame
		for i in range(res):
			if i == (res - 1):
				t = i
				break
			elif dist_map[i + 1] >= seg_len:
				t_diff = (seg_len - dist_map[i]) / (dist_map[i + 1] - dist_map[i])
				t = i + t_diff
				break
		transitions.append(t / float(res - 1))

	return transitions


def bezier_interpolation(start, end, ctrl, transitions):
	"""Interpolates a number of pixel coordinates along the length of a given quadratic bezier
	curve, based on a set of transition values from 0.0 (start point) to 1.0 (end point). The
	returned list will be the same length as the provided list of transition values.

	Args:
		start (tuple): The (x, y) coordinates of the bezier start point.
		end (tuple): The (x, y) coordinates of the bezier end point.
		ctrl (tuple): The (x, y) coordinates of the bezier control point.
		transitions (list): A list of floats between 0.0 and 1.0 (inclusive) indicating the points
			along the curve to interpolate pixel coordinates for.

	Returns:
		list: A list of (x, y) integer pixel coordinates
	"""

	# Actually compute points along bezier curve for given points
	ax, ay = (start[0] - ctrl[0], start[1] - ctrl[1])
	bx, by = (end[0] - ctrl[0], end[1] - ctrl[1])
	x = [int(ctrl[0] + ax * (1 - t) ** 2 + bx * t ** 2) for t in transitions]
	y = [int(ctrl[1] + ay * (1 - t) ** 2 + by * t ** 2) for t in transitions]

	return list(zip(x, y))
