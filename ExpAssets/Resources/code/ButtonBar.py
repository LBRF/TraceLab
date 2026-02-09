# -*- coding: utf-8 -*-
__author__ = 'jono'

import time
import sdl2

import klibs.KLParams as P
from klibs.KLConstants import RECT_BOUNDARY, CIRCLE_BOUNDARY
from klibs.KLGraphics import blit, fill, flip
from klibs.KLGraphics.KLDraw import Rectangle, Ellipse
from klibs.KLCommunication import message
from klibs.KLBoundary import BoundaryInspector
from klibs.KLUtilities import pump, flush, show_mouse_cursor, hide_mouse_cursor, mouse_pos
from klibs.KLUserInterface import ui_request
from klibs.KLEnvironment import EnvAgent


class Button(EnvAgent):

	def __init__(self, bar, button_text, button_size, location, callback=None):
		super(Button, self).__init__()
		super(EnvAgent, self).__init__()
		self.bar = bar
		self.size = button_size
		self.button_text = button_text
		self.button_rtext_a = message(button_text, "button_active", blit_txt=False)
		self.button_rtext_i = message(button_text, "button_inactive", blit_txt=False)
		self.frame_i = Rectangle(button_size[0], button_size[1], fill=None, stroke=(5, (255,255,255)))
		self.frame_a = Rectangle(button_size[0], button_size[1], fill=None, stroke=(5, (150,255,150)))
		self.active = False
		self.location = location
		self.text_location = (self.location[0] + self.size[0] // 2, self.location[1] + self.size[1] // 2)
		self.create_boundary()
		self.callback = callback

	def blit(self):
		if self.active:
			blit(self.frame_a, 5, self.location)
			blit(self.button_rtext_a, 5, self.location)
		else:
			blit(self.frame_i, 5, self.location)
			blit(self.button_rtext_i, 5, self.location)

	def create_boundary(self):
		x1 = self.location[0] - self.size[0] // 2
		y1 = self.location[1] - self.size[1] // 2
		x2 = self.location[0] + self.size[0] // 2
		y2 = self.location[1] + self.size[1] // 2
		self.bar.add_boundary(self.button_text, ((x1,y1), (x2,y2)), RECT_BOUNDARY)


class ButtonBar(BoundaryInspector, EnvAgent):

	def __init__(self, buttons, button_size, screen_margins, y_offset, message_txt=None, finish_button=True):
		super(ButtonBar, self).__init__()
		super(EnvAgent, self).__init__()
		self.txtm.add_style('button_inactive', 24, [255, 255, 255, 255])
		self.txtm.add_style('button_active', 24, [150, 255, 150, 255])
		self.b_count = len(buttons)
		self.button_data = buttons
		self.buttons = []
		try:
			self.b_width = button_size[0]
			self.b_height = button_size[1]
		except TypeError:
			self.b_width = button_size
			self.b_height = button_size
		self.screen_margins = screen_margins
		self.y_offset = y_offset
		self.b_pad = (P.screen_x - (self.b_width * self.b_count + 2 * self.screen_margins)) // (self.b_count - 1)
		self.gen_finish_button = finish_button
		self.finish_b = None
		self.message_txt = message_txt
		if message_txt:
			self.message_r = message(message, "instructions", blit_txt=False)
			self.message_loc = (P.screen_c[0], self.y_offset - (self.message_r.height * 2))
		self.gen_buttons()
		self.start = None
		self.mt = None
		self.rt = None
		self.response = None

	def gen_buttons(self):
		for b in self.button_data:
			i = self.button_data.index(b)
			loc = (self.screen_margins + (i * self.b_width) + (i * self.b_pad) + self.b_width // 2, \
				   self.y_offset + self.b_height // 2)
			try:
				self.buttons.append(Button(self, str(b[0]), (self.b_width, self.b_height), loc, b[2]))
			except IndexError:
				self.buttons.append(Button(self, str(b[0]), (self.b_width,self.b_height), loc))
		if self.gen_finish_button:
			self.finish_b = Button(self, "Done", (100,50), \
								   (P.screen_x - (self.screen_margins + self.b_width), int(P.screen_y * 0.9)))

	def render(self):
		fill()
		for b in self.buttons:
			b.blit()
		try:
			self.finish_b.blit()
		except AttributeError:
			pass
		if self.message_txt:
			blit(self.message_r, 5, self.message_loc)
		flip()

	def collect_response(self):
		self.start = time.time()
		finished = False
		selection = None
		last_selected = None
		flush()
		mt_start = None
		while not finished:
			show_mouse_cursor()
			events = pump(True)
			for e in events:
				if e.type == sdl2.SDL_KEYDOWN:
					ui_request(e.key.keysym)
				elif e.type == sdl2.SDL_MOUSEBUTTONDOWN:
					selection = None
					for b in self.buttons:
						if self.within_boundary(b.button_text, [e.button.x, e.button.y]):
							self.toggle(b)
							if not self.rt:
								self.rt = time.time() - self.start
								mt_start = time.time()
							if b.active:
								selection = b
								last_selected = b
								if callable(b.callback):
									if self.finish_b is None:
										return b.callback
									else:
										b.callback()
						try:
							if self.finish_b.active and self.within_boundary("Done",[e.button.x, e.button.y]):
								self.response = int(last_selected.button_text)
								self.mt = time.time() - mt_start
								finished = True
						except AttributeError:
							pass
			try:
				self.finish_b.active = selection is not None
			except AttributeError:
				pass
			self.render()
		fill()
		flip()
		hide_mouse_cursor()

	def toggle(self, button):
		for b in self.buttons:
			b.active = not b.active if b == button else False

	def reset(self):
		self.start = None
		self.rt = None
		self.mt = None
		self.response = None
		for b in self.buttons:
			b.active = False
		try:
			self.finish_b.active = False
		except AttributeError:
			pass

	def update_message(self, message_text):
		self.message_txt = message_text
		self.message_r = message(message_text, "instructions", blit_txt=False)
