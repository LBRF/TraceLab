# -*- coding: utf-8 -*-
__author__ = 'jono'
import klibs.KLParams as P
from klibs.KLDraw import Circle, Rectangle
from klibs.KLMixins import BoundaryInspector
from klibs.KLUtilities import *
from random import randrange

class Slider(BoundaryInspector):
	def __init__(self, experiment, y_pos, bar_length, bar_height, handle_radius, bar_fill, handle_fill):
		self.boundaries = {}
		self.exp = experiment
		self.pos = (P.screen_c[0] - bar_length // 2, y_pos)  # upper-left
		self.message_pos = (P.screen_c[0], y_pos - 50)
		self.__handle_pos = (self.pos[0], self.pos[1] + bar_height // 2)
		self.handle_color = handle_fill
		self.handle_radius = handle_radius
		self.handle_stroke = None
		self.handle_boundary = None
		self.bar = None
		self.bar_size = (bar_length, bar_height)
		self.bar_color = bar_fill
		self.bar_stroke = None
		self.show_increment_ticks = True
		self.show_increment_text = False
		self.increment_count = None
		self.increments = []
		self.increment_by = 1
		self.increment_surfs = {}
		self.lower_bound = None
		self.upper_bound = None
		self.handle = Circle(self.handle_radius * 2, fill=self.handle_color, stroke=self.handle_stroke)
		self.bar = Rectangle(self.bar_size[0], self.bar_size[1], fill=self.bar_color, stroke=self.bar_stroke)
		self.add_boundary("handle", [(self.pos[0] + self.handle_radius, self.pos[1]), self.handle_radius],
						  CIRCLE_BOUNDARY)
		self.msg = self.exp.message("How many corners did the dot traverse?", "default", blit=False)
		self.lb_msg = None
		self.ub_msg = None
		self.ok_text = self.exp.message("OK", blit=False)
		self.ok_inactive_button = Rectangle(100, 50, (1, (255,255,255)), (125,125,125)).render()
		self.ok_active_button = Rectangle(100, 50, (1, (255,255,255)), (5,175,45)).render()
		self.button_active = False
		self.button_pos = (P.screen_c[0], y_pos + bar_height + 50)
		button_upper_left = (self.button_pos[0] - 50, self.button_pos[1] - 25)
		button_botton_right = (self.button_pos[0] + 50, self.button_pos[1] + 25)
		self.add_boundary("button", (button_upper_left, button_botton_right), RECT_BOUNDARY)
		self.start_time = False

		self.response = None

	def __build_increments(self):
		self.increment_count = (self.upper_bound + 1 - self.lower_bound) // self.increment_by
		inc_width = self.bar_size[0] // self.increment_count + 1  # w/o +1 final increment has a px width of 0
		for i in range(0, self.increment_count):
			i_range = [self.pos[0] + i * inc_width, self.pos[0] + inc_width + i * inc_width]
			value = self.lower_bound + i * self.increment_by
			self.increments.append([i_range, value])
		for i in range(self.lower_bound, self.upper_bound + 1):
			self.increment_surfs[i] = (self.exp.message(str(i), "small", blit=False))

	def __update_handle_boundary(self):
		if not self.handle_pos:
			self.handle_pos = self.pos
		self.boundaries['handle'].bounds = [self.handle_pos, self.handle_radius]

	def update_range(self, seg_count):
		# this originally did some randomization around a given number and was later changed to hard values
		self.lower_bound = 1
		self.upper_bound = 5
		self.lb_msg = self.exp.message(str(self.lower_bound), "small", blit=False)
		self.ub_msg = self.exp.message(str(self.upper_bound), "small", blit=False)
		self.__build_increments()

	def slide(self):
		show_mouse_cursor()
		self.blit()

		dragging = False
		while True:
			if not dragging:
				for event in pump(True):
					self.exp.ui_request(event)
					if event.type in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONDOWN):
						within_button = self.within_boundary("button", m_pos)
						if self.button_active and within_button:
							return self.response
				m_pos = mouse_pos()
				dragging = self.within_boundary("handle", m_pos)
				if not self.start_time:
					self.start_time = P.clock.trial_time
				# if dragging:
				# 	break
			if dragging:
				button_up = False
				off_handle = False
				for event in pump(True):
					self.exp.ui_request(event)
					if event.type == sdl2.SDL_MOUSEBUTTONUP:
						button_up = True

				off_handle = not self.within_boundary("handle", mouse_pos())

				if off_handle or button_up:
					dragging = False
					self.response =  self.handle_value()
					self.button_active = True
					flush()
					return -1
				self.handle_pos = mouse_pos()[0]
				self.blit()
		return False

	def blit(self):
		self.exp.fill()
		self.exp.blit(self.ok_active_button if self.button_active else self.ok_inactive_button, 5, self.button_pos, flip_x=P.flip_x)
		self.exp.blit(self.ok_text, 5, self.button_pos, flip_x=P.flip_x)
		self.exp.blit(self.bar, 7, self.pos, flip_x=P.flip_x)
		self.exp.blit(self.handle, 5, self.handle_pos, flip_x=P.flip_x)
		self.exp.blit(self.increment_surfs[self.handle_value()], registration=5, location=self.message_pos, flip_x=P.flip_x)
		self.exp.blit(self.lb_msg, 5, (self.pos[0], self.pos[1] - 15), flip_x=P.flip_x)
		self.exp.blit(self.ub_msg, 5, (self.pos[0] + self.bar_size[0], self.pos[1] - 15), flip_x=P.flip_x)
		self.exp.blit(self.msg, 5, P.screen_c, flip_x=P.flip_x)
		self.exp.flip()

	def handle_value(self):
		for i in self.increments:
			if self.handle_pos[0] in range(i[0][0], i[0][1]):
				return i[1]

	def reset(self):
		self.response = None
		self.button_active = False
		self.handle_pos = self.pos[0]
		self.start_time = False

	@property
	def handle_pos(self):
		return self.__handle_pos

	@handle_pos.setter
	def handle_pos(self, pos):
		if pos < self.pos[0]:
			pos = self.pos[0]
		if pos > self.pos[0] + self.bar_size[0]:
			pos = self.pos[0] + self.bar_size[0] - 2
		self.__handle_pos = (pos, self.__handle_pos[1])
		self.__update_handle_boundary()
