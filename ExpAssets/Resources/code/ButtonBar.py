# -*- coding: utf-8 -*-
__author__ = 'jono'

import time

import klibs.KLParams as P
from klibs.KLGraphics import blit, fill, flip
from klibs.KLGraphics.KLDraw import Rectangle, Ellipse
from klibs.KLCommunication import message
from klibs.KLBoundary import BoundaryInspector, RectangleBoundary
from klibs.KLEventQueue import pump, flush
from klibs.KLUserInterface import ui_request, mouse_clicked, show_cursor, hide_cursor
from klibs.KLEnvironment import EnvAgent


class Button(object):

	def __init__(self, label, size, location):
		self.label = str(label)
		self.size = size
		self.location = location
		self.button_rtext_a = message(self.label, "button_active", blit_txt=False)
		self.button_rtext_i = message(self.label, "button_inactive", blit_txt=False)
		self.frame_i = Rectangle(size[0], size[1], fill=None, stroke=(5, (255,255,255)))
		self.frame_a = Rectangle(size[0], size[1], fill=None, stroke=(5, (150,255,150)))
		self.bounds = self._create_boundary(size, location)
		self.active = False

	def blit(self):
		if self.active:
			blit(self.frame_a, 5, self.location)
			blit(self.button_rtext_a, 5, self.location)
		else:
			blit(self.frame_i, 5, self.location)
			blit(self.button_rtext_i, 5, self.location)

	def _create_boundary(self, size, loc):
		xy1 = (loc[0] - size[0] // 2, loc[1] - size[1] // 2)
		xy2 = (loc[0] + size[0] // 2, loc[1] + size[1] // 2)
		return RectangleBoundary(self.label, xy1, xy2)


class ButtonBar(EnvAgent):

	def __init__(self, buttons, button_size, screen_margins, y_offset, message_txt=None, finish_button=True):
		super(ButtonBar, self).__init__()
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
		self.gen_finish_button = finish_button
		self.finish_b = None
		self.message_txt = message_txt
		if message_txt:
			self.message_r = message(message, "instructions", blit_txt=False)
			self.message_loc = (P.screen_c[0], self.y_offset - (self.message_r.height * 2))
		self.gen_buttons()
		self._loop_start = None

	def _timestamp(self):
		# Round to nearest 0.1 millisecond for more readable values
		return round(time.perf_counter(), 4)

	def gen_buttons(self):
		w, h = (self.b_width, self.b_height)
		margins = self.screen_margins
		pad = (P.screen_x - (w * self.b_count + 2 * margins)) // (self.b_count - 1)
		for b in self.button_data:
			i = self.button_data.index(b)
			loc = (margins + (i * w) + (i * pad) + w // 2, self.y_offset + h // 2)
			self.buttons.append(Button(b, (w, h), loc))
		if self.gen_finish_button:
			self.finish_b = Button(
				"Done", (100, 50), (P.screen_x - (margins + w), int(P.screen_y * 0.9))
			)

	def blit(self):
		for b in self.buttons:
			b.blit()
		if self.finish_b:
			self.finish_b.blit()

	def render(self):
		fill()
		self.blit()
		if self.message_txt:
			blit(self.message_r, 5, self.message_loc)
		flip()

	def collect(self):
		"""Renders and collects a response from the button bar.

		Response format is `(button, elapsed)` if the button bar has no response
		button, or `(button, rt_first, rt_final, elapsed)`:
		  * 'button' is the label of the response button.
		  * 'elapsed' is the duration (in seconds) between the start and end of
		     the collection loop.
		  * 'rt_first' is the reaction time (in seconds) for the participant's
		     first button selection.
		  * 'rt_final' is the reaction time (in seconds) for the participant's
		     final buttion selection. Only different from 'rt_first' if the
			 participant changes their response before submitting.

		"""
		rt_first = None
		rt_final = None
		choice = None
		resp = None
		self.render()
		self.init()
		while not resp:
			events = pump()
			# If no finish button provided, return as soon as a button is clicked
			if self.finish_b is None:
				for b in self.buttons:
					if mouse_clicked(within=b.bounds, queue=events):
						choice = b.label
						elapsed = self._timestamp() - self._loop_start
						resp = (choice, elapsed)
						break
			else:
				# Check if any button has been clicked, changing its state if so
				for b in self.buttons:
					if mouse_clicked(within=b.bounds, queue=events):
						self.toggle(b)
						choice = b.label if b.active else None
						self.finish_b.active = True if b.active else False
						if not rt_first:
							rt_first = (self._timestamp() - self._loop_start)
						rt_final = (self._timestamp() - self._loop_start)
				# If a response has been made and finish button clicked, return response
				if self.finish_b.active:
					if mouse_clicked(within=self.finish_b.bounds, queue=events):
						elapsed = self._timestamp() - self._loop_start
						resp = (choice, rt_first, rt_final, elapsed)
						break
			self.render()
		self.cleanup()
		return resp

	def init(self):
		flush()
		show_cursor()
		self._loop_start = self._timestamp()

	def cleanup(self):
		hide_cursor()
		for b in self.buttons:
			b.active = False
		if self.finish_b:
			self.finish_b.active = False

	def toggle(self, button):
		for b in self.buttons:
			b.active = not b.active if b == button else False

	def update_message(self, message_text):
		self.message_txt = message_text
		self.message_r = message(message_text, "instructions", blit_txt=False)
