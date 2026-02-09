import sdl2


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
