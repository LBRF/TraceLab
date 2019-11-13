__author__ = 'jono'

import re
import sys
import traceback

from os.path import join
from time import time
from sdl2 import SDL_KEYDOWN, SDLK_DELETE
from PIL import Image
import numpy as np

from klibs import P
from klibs.KLJSON_Object import JSON_Object
from klibs.KLBoundary import RectangleBoundary
from klibs.KLUserInterface import ui_request
from klibs.KLUtilities import line_segment_len, scale, pump
from klibs.KLUtilities import colored_stdout as cso
from klibs.KLGraphics import blit, flip, fill
from klibs.KLGraphics.KLDraw import Rectangle, Ellipse, Annulus
from klibs.KLCommunication import message
from klibs.KLAudio import AudioClip


from drawingutils import (bezier_bounds, bezier_length, bezier_transitions, bezier_interpolation,
	linear_transitions, linear_interpolation)

# TODO: come up with a way for a FrameSet object to be an asset
AUDIO_FILE = "audio_f"
IMAGE_FILE = "image_f"


def is_string(s):
	# Python 2/3 agnostic of determining whether object is a string
	return isinstance(s, ("".__class__, u"".__class__))


class KeyFrameAsset(object):

	def __init__(self, data):

		self.media_type = IMAGE_FILE
		self.height = None
		self.width = None
		self.duration = None

		if data.text:
			# todo: make style optional
			self.contents = message(data.text.string, data.text.style, align="center", blit_txt=False)
		elif data.drawbject:
			d = data.drawbject
			if d.shape == "rectangle":
				self.contents = Rectangle(d.width, d.height, d.stroke, d.fill).render()
			if d.shape == "ellipse":
				self.contents = Ellipse(d.width, d.height, d.stroke, d.fill).render()
			if d.shape == "annulus":
				self.contents = Annulus(d.diameter, d.ring_width, d.stroke, d.fill).render()
		else:
			self.media_type = data.file.media_type
			if self.is_audio:
				self.duration = data.file
				self.contents = AudioClip(join(P.resources_dir, "audio", data.file.filename))
			else:
				# If asset is image file, import and scale for current screen size (animations
				# originally hard-coded at 1920x1080 so we scale relative to that)
				img = Image.open(join(P.image_dir, data.file.filename))
				target_size = (P.screen_x, (P.screen_x / 16.0) * 9) # corrected for aspect ratio
				scaled_size = scale(img.size, (1920, 1080), target_size, center=False)
				self.contents = np.asarray(img.resize(scaled_size, Image.BILINEAR))

		try:
			self.height = self.contents.height
			self.width = self.contents.width
		except AttributeError:
			try:
				self.height = self.contents.shape[0]
				self.width = self.contents.shape[1]
			except AttributeError:
				pass  # ie. audio file

	@property
	def is_image(self):
		return self.media_type == IMAGE_FILE

	@property
	def is_audio(self):
		return self.media_type == AUDIO_FILE



class KeyFrame(object):

	def __init__(self, data, assets):
		self.assets = assets
		self.label = data.label
		self.directives = data.directives
		self.duration = data.duration * 0.001
		self.asset_frames = []
		self.enabled = data.enabled
		self.audio_track = None
		self.audio_start_time = 0
		self.screen_bounds = RectangleBoundary('screen', (0, 0), P.screen_x_y)
		if self.enabled:
			self.__render_frames__()

	def key_pressed(self, keysym, queue=None):
		pressed = False
		if not queue:
			queue = pump(True)
		for e in queue:
			if e.type == SDL_KEYDOWN:
				ui_request(e.key.keysym)
				if e.key.keysym.sym == keysym:
					pressed = True
					break
		return pressed
	
	def play(self):
		try:
			if self.audio_track.started:
				self.audio_track.started = False
		except AttributeError:
			pass
		start = time()
		frames_played = False
		while time() - start < self.duration:
			if self.key_pressed(SDLK_DELETE):
				try:
					self.audio_track.stop()
				except AttributeError:
					pass
				return True
			if not frames_played:
				for frame in self.asset_frames:
					try:
						if time() - start >= self.audio_start_time and not self.audio_track.started:
							self.audio_track.play()
							self.audio_track.started = True
					except AttributeError:
						pass
					if self.key_pressed(SDLK_DELETE):
						try:
							self.audio_track.stop()
						except AttributeError:
							pass
						return True
					fill()
					for asset in frame:
						blit(asset[0], asset[2], asset[1])
					flip()
				frames_played = True

		return False

	def __render_frames__(self):
		total_frames = 0
		asset_frames = []
		num_static_directives = 0
		img_drctvs = []
		try:
			# strip out audio track if there is one, first
			for d in self.directives:

				for key in ['start', 'end']:
					if key in d.keys() and is_string(d[key]):
						eval_statement = re.match(re.compile(u"^EVAL:[ ]*(.*)$"), d[key])
						d[key] = eval(eval_statement.group(1))

				try:
					asset = self.assets[d.asset].contents
				except KeyError:
					e_msg = "Asset '{0}' not found in KeyFrame.assets.".format(d.asset)
					raise KeyError(e_msg)

				if self.assets[d.asset].is_audio:
					if self.audio_track is not None:
						raise RuntimeError("Only one audio track per key frame can be set.")
					else:
						self.audio_track = self.assets[d.asset].contents
						self.audio_start_time = d.start * 0.001
				else:
					# Scale pixel values from 1920x1080 to current screen resolution
					d.start = scale(d.start, (1920,1080))
					d.end = scale(d.end, (1920,1080))
					if "control" in d.keys():
						d.control = scale(d.control, (1920,1080))
					img_drctvs.append(d)
					if d.start == d.end:
						num_static_directives += 1

			if len(img_drctvs) == num_static_directives:
				self.asset_frames = [
					[(self.assets[d.asset].contents, d.start, d.registration) for d in img_drctvs]
				]
				return

			for d in img_drctvs:

				for key in ['start', 'end']:
					if is_string(d[key]):
						eval_statement = re.match(re.compile(u"^EVAL:[ ]*(.*)$"), d[key])
						d[key] = eval(eval_statement.group(1))

				asset = self.assets[d.asset].contents
				if d.start == d.end:
					asset_frames.append([(asset, d.start, d.registration)])
					continue

				frames = []
				if "control" in d.keys(): # if bezier curve
					bounds = bezier_bounds(d.start, d.control, d.end)
					if not all([self.screen_bounds.within(p) for p in bounds]):
						txt = "KeyFrame {0} does not fit in drawable area and will not be rendered."
						cso("<red>\tWarning: {0}</red>".format(txt.format(self.label)))
						continue
					fps = P.refresh_rate
					path_len = bezier_length(d.start, d.control, d.end)
					vel = path_len / (self.duration * 1000.0)
					transitions = bezier_transitions(d.start, d.control, d.end, vel, fps)
					raw_frames = bezier_interpolation(d.start, d.end, d.control, transitions)
				else: # if not a bezier curve, it's aline
					try:
						vel = line_segment_len(d.start, d.end) / (self.duration * 1000.0)
					except TypeError:
						raise ValueError("Image assets require their 'start' and 'end' attributes to be an x,y pair.")
					transitions = linear_transitions(d.start, d.end, vel, fps=P.refresh_rate)
					raw_frames = linear_interpolation(d.start, d.end, transitions)

				for p in raw_frames :
					frames.append([asset, p, d.registration])
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

		except (IndexError, AttributeError, TypeError) as e:
			err = (
				"An error occurred when rendering this frame."
				"This is usually do an unexpected return from an 'EVAL:' entry in the JSON script."
				"The error occurred in keyframe {0} and the last attempted directive was:"
			)
			print(err.format(self.label))
			print("\nThe original error was:\n")
			traceback.print_exception(*sys.exc_info())
			raise e


class FrameSet(object):

	def __init__(self, key_frames_file, assets_file=None):
		self.key_frames = []
		self.assets = {}
		if assets_file:
			self.assets_file = join(P.resources_dir, "code", assets_file + ".json")
		else:
			self.assets_file = None
		self.key_frames_file = join(P.resources_dir, "code", key_frames_file + ".json")
		self.generate_key_frames()

	def __load_assets__(self, assets_file):
		j_ob = JSON_Object(assets_file)
		for a in j_ob:
			self.assets[a] = KeyFrameAsset(j_ob[a])

	def generate_key_frames(self):
		if self.assets_file:
			self.__load_assets__(self.assets_file)
		j_ob = JSON_Object(self.key_frames_file)
		for kf in j_ob.keyframes:
			self.key_frames.append(KeyFrame(kf, self.assets))

	def play(self):
		ui_request()
		for kf in self.key_frames:
			if kf.enabled:
				skip = kf.play()
				if skip:
					break
