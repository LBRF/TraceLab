# -*- coding: utf-8 -*-
__author__ = 'jono'
import sdl2

import klibs.KLParams as P
from klibs.KLConstants import RECT_BOUNDARY, CIRCLE_BOUNDARY
from klibs.KLGraphics import blit, fill, flip, clear
from klibs.KLGraphics.KLDraw import Circle, Rectangle, Ellipse, Annulus
from klibs.KLCommunication import message
from klibs.KLBoundary import BoundaryInspector, RectangleBoundary
from klibs.KLUtilities import *
from klibs.KLUtilities import line_segment_len as lsl
from klibs.KLUserInterface import ui_request, key_pressed
from klibs.KLEnvironment import EnvAgent
from random import randrange

from klibs.KLBoundary import RectangleBoundary


class LikertType(EnvAgent):

	def __init__(self, first, last, width, registration=None, location=None,
				 gap=2, question=None):
		EnvAgent.__init__(self)

		self.range = range(first, last+1, 1)
		self.count = len(self.range)
		self.width = width
		self.gap = gap
		self.response = None
		
		self.question = question

		self.circle_size = int((float(width)/self.count) - (float(gap)/(self.count+1)))
		self.height = self.circle_size + self.gap*2

		self.__init_bounds__(registration, location)

		self.txtm.add_style("likert_num", 20, color=(255,255,255))
		numlist = []
		for num in self.range:
		    num_txt = message("{0}".format(num), "likert_num", blit_txt=False)
		    numlist.append((num, num_txt))
		self.numbers = dict(numlist)

		self.selected = Ellipse(self.circle_size, fill=[192,192,192,64])
		self.mouseover = Annulus(self.circle_size, 6, fill=[128,128,128,255])

	def __render__(self):
		if self.question != None:
			blit(*self.question)
		for num in self.range:
			pos = self.__num_to_pos__(num)
			blit(self.numbers[num], location=pos, registration=5)
		if self.response != None:
			pos = self.__num_to_pos__(self.response)
			blit(self.selected, location=pos, registration=5)

	def __init_bounds__(self, registration, location):
		
		if not location:
			location = P.screen_c
		if not registration:
			registration = 5

		if registration in [7, 4, 1]:
			self.x_offset = self.width // 2
		elif registration in [9, 6, 3]:
			self.x_offset = -self.width // 2
		else:
			self.x_offset = 0	
		if registration in [7, 8, 9]:
			self.y_offset = self.height // 2
		elif registration in [1, 2, 3]:
			self.y_offset = -self.height // 2
		else:
			self.y_offset = 0		

		self.midpoint = (location[0]+self.x_offset, location[1]+self.y_offset)
		self.x1 = self.midpoint[0] - self.width//2
		self.y1 = self.midpoint[1] - self.height//2
		self.x2 = self.midpoint[0] + self.width//2
		self.y2 = self.midpoint[1] + self.height//2
		self.bounds = RectangleBoundary("likert", (self.x1, self.y1), (self.x2, self.y2))
	
	def __num_to_pos__(self, num):
		n = self.range.index(num)
		select_w = self.gap + self.circle_size
		x_pos = (self.x1 + int(select_w*(n+0.5)))
		y_pos = (self.y1 + int(select_w*0.5))
		return (x_pos, y_pos)

	def response_listener(self, queue):
		self.__render__()
		mp_abs = mouse_pos()
		if self.bounds.within(mp_abs):
			mouse_loc = (mp_abs[0]-self.x1, mp_abs[1]-self.y1)
			select_w = self.circle_size + self.gap
			index = int(round(mouse_loc[0] // select_w))
			nearest_x = index * select_w + (select_w//2)
			within_circle = lsl(mouse_loc, (nearest_x, (select_w//2))) < (self.circle_size * 0.6)
			# Display ring around response mouse is currently hovering over and
			# record clicks as response selections.
			if within_circle:
				blit(self.mouseover, 5, (self.x1+nearest_x, self.midpoint[1]))
				for e in queue:
					if e.type == sdl2.SDL_MOUSEBUTTONDOWN:
						self.response = self.range[index]
	
	def collect(self):
		show_mouse_cursor()
		while True:
			q = pump(True)
			for event in q:
				ui_request(event)
			fill()
			self.response_listener(q)
			flip()
			if self.response != None and key_pressed(sdl2.SDLK_RETURN, queue=q):
				clear()
				return self.response


class Slider(BoundaryInspector, EnvAgent):
	def __init__(self, y_pos, bar_length, bar_height, handle_radius, bar_fill, handle_fill):
		BoundaryInspector.__init__(self)
		EnvAgent.__init__(self)
		self.boundaries = {}
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
		self.msg = message("How many corners did the dot traverse?", "default", blit_txt=False)
		self.lb_msg = None
		self.ub_msg = None
		self.ok_text = message("OK", blit_txt=False)
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
			self.increment_surfs[i] = (message(str(i), "small", blit=False))

	def __update_handle_boundary(self):
		if not self.handle_pos:
			self.handle_pos = self.pos
		self.boundaries['handle'].bounds = [self.handle_pos, self.handle_radius]

	def update_range(self, seg_count):
		# this originally did some randomization around a given number and was later changed to hard values
		self.lower_bound = 1
		self.upper_bound = 5
		self.lb_msg = message(str(self.lower_bound), "small", blit=False)
		self.ub_msg = message(str(self.upper_bound), "small", blit=False)
		self.__build_increments()

	def slide(self):
		show_mouse_cursor()
		self.blit()

		dragging = False
		while True:
			if not dragging:
				m_pos = mouse_pos()
				for event in pump(True):
					ui_request(event)
					if event.type in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONDOWN):
						within_button = self.within_boundary("button", m_pos)
						if self.button_active and within_button:
							return self.response
				dragging = self.within_boundary("handle", m_pos)
				if not self.start_time and dragging:
					self.start_time = P.clock.trial_time
			if dragging:
				button_up = False
				off_handle = False
				for event in pump(True):
					ui_request(event)
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
		fill()
		blit(self.ok_active_button if self.button_active else self.ok_inactive_button, 5, self.button_pos, flip_x=P.flip_x)
		blit(self.ok_text, 5, self.button_pos, flip_x=P.flip_x)
		blit(self.bar, 7, self.pos, flip_x=P.flip_x)
		blit(self.handle, 5, self.handle_pos, flip_x=P.flip_x)
		blit(self.increment_surfs[self.handle_value()], registration=5, location=self.message_pos, flip_x=P.flip_x)
		blit(self.lb_msg, 5, (self.pos[0], self.pos[1] - 15), flip_x=P.flip_x)
		blit(self.ub_msg, 5, (self.pos[0] + self.bar_size[0], self.pos[1] - 15), flip_x=P.flip_x)
		blit(self.msg, 5, P.screen_c, flip_x=P.flip_x)
		flip()

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
				ui_request(e)
				if e.type == sdl2.SDL_MOUSEBUTTONDOWN:
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

