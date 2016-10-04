__author__ = 'jono'
import abc
import time
import os
import json
import unicodedata
from re import compile
from math import floor
from klibs import P
from klibs.KLNumpySurface import NumpySurface as NpS
from klibs.KLDraw import *
from klibs.KLUtilities import line_segment_len, iterable
from TraceLabFigure import interpolated_path_len, bezier_interpolation, pascal_row, linear_interpolation

# TODO: come up with a way for a FrameSet object to be an asset

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


class JSON_Object(object):
	__eval_regex__ = compile("^EVAL:[ ]{0,}(.*)$")

	def __init__(self, json_file_path=None, decoded_data=None, child_object=False):
		try:
			self.__items__ = self.__unicode_to_str__(json.load(open(json_file_path)) if json_file_path else decoded_data)
		except ValueError:
			raise ValueError("JSON file is poorly formatted. Please check syntax.")
		self.__objectified__ = self.__objectify__(self.__items__, not (child_object and type(decoded_data) is list))
		self.__current__ = 0
		try:
			self.keys = self.__items__.keys()
			self.values = []
			for k in self.keys:
				self.values.append(self.__dict__[k])
		except AttributeError:
			self.keys = range(0, len(self.__items__))
			self.values = self.__items__

	def __unicode_to_str__(self, content):
		if type(content) is unicode:
			# convert string to ascii
			converted = unicodedata.normalize('NFKD', content).encode('ascii','ignore')

			# convert JS booleans to Python booleans
			if converted in ("true", "false"):
				converted = converted == "true"

			# run eval on Python code passed as a JSON string
			eval_statement = self.__eval_regex__.match(converted)
			if eval_statement is not None:
				converted = eval(eval_statement.group(1))
				if type(converted) is tuple:
					converted = list(converted)
				# todo: this next bit is broken, it's so unimportant I didn't even try to fix it but maybe one day
				# on the off chance that the eval returns well-formed JSON
				# try:
				# 	converted = JSON_Object(converted)
				# except ValueError:
				# 	pass

		elif type(content) in (list, dict):
			#  manage dicts first
			try:
				converted = {}  # converted output for this level of the data
				for k in content:
					v = content[k]  # ensure the keys are ascii strings
					if type(k) is unicode:
						k = self.__unicode_to_str__(k)
					if type(v) is unicode:
						converted[k] = self.__unicode_to_str__(v)
					elif iterable(v):
						converted[k] = self.__unicode_to_str__(v)
					else:
						converted[k] = v

			except (TypeError, IndexError):
				converted = []
				for i in content:
					if type(i) is unicode:
						converted.append(self.__unicode_to_str__(i))
					elif iterable(i):
						converted.append(self.__unicode_to_str__(i))
					else:
						converted.append(i)

		else:
			# assume it's numeric
			return content

		return converted

	def __find_nested_dicts__(self, data):
		tmp = []
		for i in data:
			if type(i) is dict:
				tmp.append(JSON_Object(None, i, True))
			elif type(i) is list:
				tmp.append(self.__find_nested_dicts__(i))
			else:
				tmp.append(i)
		return tmp

	def __objectify__(self, content, initial_pass=False):

		try:
			converted = {}
			for i in content:
				v = content[i]
				if type(v) is dict:
					v = JSON_Object(None, v, True)
				elif type(v) is list:
					v = self.__find_nested_dicts__(v)
				converted[i] = v
				if initial_pass:
					setattr(self, i, v)
		except (TypeError, IndexError) as e:
			if initial_pass:
				raise ValueError("Top-level element must be a key-value pair.")
			converted = []
			for i in content:
				if type(i) is dict:
					converted.append(JSON_Object(None, i, True))
				elif type(i) is list:
					converted.append(self.__find_nested_dicts__(i))
				else:
					converted.append(i)
		return converted


	def __iter__(self):
		return self

	def __getitem__(self, key):
		return self.__dict__[key]

	def next(self):
		try:
			i =  self.keys[self.__current__]
			self.__current__ += 1
			return i
		except IndexError:
			self.__current__ = 0
			raise StopIteration

	def report(self, depth=0, subtree=None):
		keys = self.keys if not subtree else subtree
		vals = self.__items__ if not subtree else subtree.__items__
		for k in keys:
			if isinstance(vals[k], JSON_Object):
				print "{0}".format(depth * "\t" + k)
				self.report(depth + 1, vals[k])
			else:
				print "{0}: {1}".format(depth * "\t" + k, vals[k])


class KeyFrameAsset(object):

	def __init__(self, exp, data):
		self.exp = exp
		if data.text:
			# todo: make style optional
			self.contents = exp.message(data.text.string, data.text.style, blit=False)
		elif data.filename:
			self.contents = NpS(os.path.join(P.image_dir, data.filename))
		elif data.drawbject:
			d = data.drawbject
			if d.shape == "rectangle":
				self.contents = Rectangle(d.width, d.height, d.stroke, d.fill)
			if d.shape == "ellipse":
				self.contents = Ellipse(d.width, d.height, d.stroke, d.fill)
			if d.shape == "annulus":
				self.contents = Annulus(d.diameter, d.ring_width, d.stroke, d.fill)

class KeyFrame(object):

	def __init__(self, exp, data, assets):
		self.exp = exp
		self.assets = assets
		self.label = data.label
		self.directives = data.directives
		self.duration = data.duration * 0.001
		self.asset_frames = []
		self.enabled = data.enabled
		if self.enabled:
			self.__render_frames__()

	def play(self):
		start = time.time()
		for frame in self.asset_frames:
			self.exp.ui_request()
			self.exp.fill()
			for asset in frame:
				self.exp.blit(self.assets[asset[0]].contents, 5, asset[1])
			self.exp.flip()
		while time.time() - start < self.duration:
			self.exp.ui_request()

	def __render_frames__(self):
		total_frames = 0
		asset_frames = []
		try:
			if all([d.start == d.end for d in self.directives]):
				self.asset_frames = [[[d.asset, d.start] for d in self.directives]]
				return
			for d in self.directives:
				if d.start == d.end:
					asset_frames.append([[d.asset, d.start]])
					continue
				frames = []
				try:
					path_len = bezier_interpolation(d.start, d.end, d.control)[0]
					raw_frames = bezier_interpolation(d.start, d.end, d.control, velocity=path_len / self.duration)
				except AttributeError:
					v = line_segment_len(d.start, d.end) / self.duration
					raw_frames = linear_interpolation(d.start, d.end, v)
				for p in raw_frames :
					frames.append([d.asset, p])
				if len(frames) > total_frames:
					total_frames = len(frames)
				asset_frames.append(frames)
			for frame_set in asset_frames:
				while len(frame_set) < total_frames:
					frame_set.append(frame_set[-1])
			self.asset_frames = []
			if total_frames > 1:
				for i in range(0, total_frames):
					self.asset_frames.append([n[i] for n in asset_frames])
			else:
				self.asset_frames = asset_frames
		except Exception as e:
			for d in self.directives: print d
			e_msg = "An error occurred when rendering this frame. This is usually do an unexpected return " \
					"from an 'EVAL:' entry in the JSON script. The original error was:\n\n\t{0}: {1}".format(e.__class__, e.message)
			raise RuntimeError(e_msg)


class FrameSet(object):

	def __init__(self, exp, key_frames_file, assets_file=None):
		self.exp = exp
		self.key_frames = []
		self.assets = {}
		if assets_file:
			self.assets_file = os.path.join(P.resources_dir, "code", assets_file + ".json")
		else:
			self.assets_file = None
		self.key_frames_file = os.path.join(P.resources_dir, "code", key_frames_file + ".json")
		self.generate_key_frames()


	def __load_assets__(self, assets_file):
		j_ob = JSON_Object(assets_file)
		for a in j_ob:
			self.assets[a] = KeyFrameAsset(self.exp, j_ob[a])

	def generate_key_frames(self, ):
		if self.assets_file:
			self.__load_assets__(self.assets_file)
		j_ob = JSON_Object(self.key_frames_file)
		for kf in j_ob.keyframes:
			print kf.label
			self.key_frames.append(KeyFrame(self.exp, kf, self.assets))


	def play(self):
		for kf in self.key_frames:
			if kf.enabled:
				kf.play()
