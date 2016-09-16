__author__ = 'jono'
import abc
import time
import os
from math import floor
from klibs import P
from klibs.KLConstants import *
from klibs.KLNumpySurface import NumpySurface as NpS
from klibs.KLDraw import *
from klibs.KLUtilities import line_segment_len
from TraceLabFigure import interpolated_path_len, bezier_interpolation, pascal_row, linear_interpolation


def bezier_frames(self):
		self.path_length = interpolated_path_len(self.frames)
		draw_in = self.animate_target_time * 0.001
		rate = 0.016666666666667
		max_frames = int(draw_in / rate)
		delta_d = floor(self.path_length / max_frames)
		self.a_frames = [list(self.frames[0])]
		seg_len = 0
		for i in range(0, len(self.frames)):
			p1 = [float(p) for p in self.frames[i]]
			try:
				p2 = [float(p) for p in self.frames[i+1]]
			except IndexError:
				p2 = [float(p) for p in self.frames[0]]
			seg_len += line_segment_len(p1, p2)
			if seg_len >= delta_d:
				self.a_frames.append(list(self.frames[i]))
				seg_len = 0


class KeyFrameAsset(object):

	def __init__(self, text=None, file_name=None, drawbject=None):
		if not text and not file_name and not drawbject:
			raise ValueError("No resource provided.")
		if text:
			self.contents = text
		if file_name:
			self.contents = NpS(os.path.join(P.image_dir, file_name))
		if drawbject:
			if drawbject[0] == "rect":
				self.contents = Rectangle(*drawbject[1:])
			if drawbject[0] == "ellipse":
				self.contents = Ellipse(*drawbject[1:])
			if drawbject[0] == "annulus":
				self.contents = Annulus(*drawbject[1:])

class KeyFrame(object):

	def __init__(self, duration, assets, directives, cl_after=False, cl_before=False):
		self.exp = None
		self.duration = duration * 0.001
		self.cl_after = cl_after
		self.cl_before = cl_before
		self.assets = assets
		self.directives = directives
		self.asset_frames = []

	def play(self):
		start = time.time()
		if self.cl_before:
			self.exp.fill()
		for t in self.asset_frames:
			self.exp.fill()
			for a in t:
				self.exp.blit(self.assets[a[0]], 5, a[1])
			self.flip()
		if self.clear_after:
			self.exp.fill()
		while time.time() - start < self.duration:
			self.exp.ui_request()

	def __render_frames__(self):
		total_frames = 0
		asset_frames = []
		for d in self.directives:
			if d[1] == d[2]:
				asset_frames.append([d[0], d[1]])
				continue
			frames = []
			if d[3] is None:
				v = line_segment_len(d[1], d[2]) / self.duration
				raw_frames = linear_interpolation(d[1], d[2], v)
			else:
				v = interpolated_path_len(bezier_interpolation(d[1, d[2], d[3]])) / self.duration
				raw_frames = bezier_interpolation(d[1, d[2], d[3]], None, v)
			for p in raw_frames :
				frames.append([d[0], p])
			if len(frames) > total_frames:
				total_frames = len(frames)
			asset_frames.append(frames)
		for frame_set in asset_frames:
			while len(frame_set) < total_frames:
				frame_set.append(frame_set[-1])
		self.asset_frames = []
		for i in range(0, len(asset_frames)):
			self.asset_frames.append([n[i] for n in asset_frames])

class FrameSet(object):

	def __init__(self):
		self.key_frames = []
		self.assets = {}

	def load_assets(self, asset_list):
		for a in asset_list:
			self.assets[a] = KeyFrameAsset(asset_list[a])

	def gen_key_frames(self, kf_list):
		for kf in kf_list:
			self.key_frames.append(KeyFrame(kf[1], self.assets, kf[2]))

	def play(self):
		for kf in self.key_frames:
			kf.play()
asset_list = [['pointer', None, "pointer.png", None],
			  ['dot', None, None, ["annulus", 6,2,[1, (255,255,255)], (255, 0,0)]],
			  ['instrux', "This is some instruction text", None, None]]
keyframes = [["instructions", 1000, [["instrux", P.screen_c, P.screen_c]]],
			 ["dot animate", 3000, [["dot", P.screen_c, (500,500)]]],
			 ["both animate", 3000, [["dot", P.screen_c, (500,500)],
									 ["pointer", (0,0), (500, 500)]]]]