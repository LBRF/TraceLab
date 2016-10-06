__author__ = 'jono'
# import sys
# sys.path.append("ExpAssets/Resources/code/")

from klibs import P
from klibs.KLNumpySurface import NumpySurface as NpS
from klibs.KLDraw import *
from klibs.KLAudio import AudioClip
from klibs.KLUtilities import line_segment_len
from TraceLabFigure import bezier_interpolation,  linear_interpolation
from JSON_Object import JSON_Object

# TODO: come up with a way for a FrameSet object to be an asset
AUDIO_FILE = "audio_f"
IMAGE_FILE = "image_f"

class KeyFrameAsset(object):

	def __init__(self, exp, data):
		self.exp = exp
		self.media_type = IMAGE_FILE
		self.height = None
		self.width = None
		self.duration = None

		if data.text:
			# todo: make style optional
			self.contents = exp.message(data.text.string, data.text.style, blit=False)
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
				self.contents = AudioClip(os.path.join(P.resources_dir, "audio", data.file.filename))
			else:
				self.contents = NpS(os.path.join(P.image_dir, data.file.filename))

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

	def __init__(self, exp, data, assets):
		self.exp = exp
		self.assets = assets
		self.label = data.label
		self.directives = data.directives
		self.duration = data.duration * 0.001
		self.asset_frames = []
		self.enabled = data.enabled
		self.audio_track = None
		self.audio_start_time = 0
		if self.enabled:
			self.__render_frames__()

	def play(self):
		start = time.time()
		frames_played = False
		while time.time() - start < self.duration:
			self.exp.ui_request()
			# if self.audio_track:
			try:
				if time.time() - start >= self.audio_start_time and not self.audio_track.started:
					self.audio_track.play()
			except AttributeError:
				pass
			if not frames_played:
				for frame in self.asset_frames:
					self.exp.ui_request()
					self.exp.fill()
					for asset in frame:
						self.exp.blit(asset[0], 5, asset[1])
					self.exp.flip()
				frames_played = True

	def __render_frames__(self):
		total_frames = 0
		asset_frames = []
		num_static_directives = 0
		img_drctvs = []

		try:
			# strip out audio track if there is one, first
			for d in self.directives:
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
						self.audio_start_time = d.start
				else:
					img_drctvs.append(d)
					if d.start == d.end:
						num_static_directives += 1


			if len(img_drctvs) == num_static_directives:
				self.asset_frames = self.asset_frames = [[(self.assets[d.asset].contents, d.start) for d in img_drctvs]]
				return

			for d in img_drctvs:
				asset = self.assets[d.asset].contents
				if d.start == d.end:
					asset_frames.append([(asset, d.start)])
					continue
				frames = []
				try:
					path_len = bezier_interpolation(d.start, d.end, d.control)[0]
					raw_frames = bezier_interpolation(d.start, d.end, d.control, velocity=path_len / self.duration)
				except AttributeError:
					v = line_segment_len(d.start, d.end) / self.duration
					raw_frames = linear_interpolation(d.start, d.end, v)
				for p in raw_frames :
					frames.append([asset, p])
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

		except (IndexError, AttributeError, TypeError, ValueError) as e:
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
			self.key_frames.append(KeyFrame(self.exp, kf, self.assets))


	def play(self):
		for kf in self.key_frames:
			if kf.enabled:
				kf.play()
