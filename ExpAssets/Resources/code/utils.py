import socket
import ctypes

import sdl2
import klibs.KLParams as P


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
