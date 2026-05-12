import socket
import ctypes

import sdl2
import OpenGL.GL as gl

import klibs.KLParams as P
from klibs.KLGraphics import rgb_to_rgba

WHITE = (255, 255, 255, 255)


def fast_rect(x1, y1, x2, y2, color):
	"""Draws a solid rectangle of a given colour quickly to the screen.

	This draws a rectangle directly to the backbuffer, avoiding the need to create a
	texture and copy it to the GPU every frame and thus making it much faster for large
	rectangles. Useful when timing is important.

	"""
	# Sets the draw colour for the rectangle
	r, g, b, a = rgb_to_rgba(color)
	gl.glColor4ub(r, g, b, a)
	# Draws the rectangle directly to the backbuffer
	gl.glBegin(gl.GL_TRIANGLE_STRIP)
	gl.glVertex2f(x1, y1)
	gl.glVertex2f(x1, y2)
	gl.glVertex2f(x2, y1)
	gl.glVertex2f(x2, y2)
	gl.glEnd()


def draw_borders(size, color=WHITE):
	# Draws borders to the screen edges to make them clearly visible
	w, h = P.screen_x_y
	fast_rect(0, 0, w, size, color) # top
	fast_rect(0, 0, size, h, color) # left
	fast_rect(0, h - size, w, h, color) # bottom
	fast_rect(w - size, 0, w, h, color) # right


def touchscreen_detected():
	# Attempts to detect any available touchscreens
	n = sdl2.SDL_GetNumTouchDevices()
	# NOTE: On Windows, touchscreen must be touched at least once after task
    # start for it to be detected as a touch device
	for i in range(n):
		dev = sdl2.SDL_GetTouchDevice(i)
		devtype = sdl2.SDL_GetTouchDeviceType(dev)
		if devtype == sdl2.SDL_TOUCH_DEVICE_DIRECT:
			return True
	return False


def get_touch_coords():
	# Returns the x/y coordinates of the mouse cursor (if finger on screen)
    sdl2.SDL_PumpEvents()
    cx, cy = ctypes.c_int(0), ctypes.c_int(0)
    b_state = sdl2.SDL_GetMouseState(ctypes.byref(cx), ctypes.byref(cy))
    x = int(cx.value * P.screen_scale_x)
    y = int(cy.value * P.screen_scale_y)
    lifted = (b_state & sdl2.SDL_BUTTON(sdl2.SDL_BUTTON_LEFT)) == 0
    return None if lifted else (x, y)


def get_hostname():
    # Gets and sanitizes the hostname of the current computer
	hostname = socket.gethostname()
	for a, b in [(".local", ""), ("DESKTOP-", ""), (" ", "-")]:
		hostname = hostname.replace(a, b)
	return hostname
