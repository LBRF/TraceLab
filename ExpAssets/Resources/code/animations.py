from time import perf_counter

from klibs import P
from klibs.KLUtilities import line_segment_len

from drawingutils import (
    bezier_length, bezier_transitions, bezier_interpolation,
	linear_transitions, linear_interpolation
)


class Keyframe(object):
    """An animation without any actual movement.

    Allows for the easy insertion of pauses into `run_animation`.

    """
    def __init__(self, position, duration):
        self._position = position
        self._duration = duration
        self._start = None
        self.done = False

    def reset(self):
        self._start = None
        self.done = False

    @property
    def position(self):
        if not self._start:
            self._start = perf_counter()
        elif not self.done:
            elapsed = perf_counter() - self._start
            if elapsed >= self._duration:
                self.done = True
        return self._position
    

class Animation(object):
    """Generates a linear or bezier animation with a given duration.

    """
    def __init__(self, start, end, control=None, duration=1.0):
        self.start = start
        self.end = end
        self.control = control
        self.duration = duration
        self.frame = 0
        self.done = False
        self.frames = self._generate_frames(start, end, control, duration)

    def _generate_frames(self, start, end, ctrl, duration):
        # NOTE: Could probably rewrite to get coordinates for a given timepoint instead
        #       of pre-rendering all frames if variable frame rate is ever an issue.
        if ctrl is not None:
            path_len = bezier_length(start, ctrl, end)
            velocity = path_len / (duration * 1000.0)
            transitions = bezier_transitions(start, ctrl, end, velocity, P.refresh_rate)
            return bezier_interpolation(start, end, ctrl, transitions)
        else:
            velocity = line_segment_len(start, end) / (duration * 1000.0)
            transitions = linear_transitions(start, end, velocity, P.refresh_rate)
            return linear_interpolation(start, end, transitions)

    def reset(self):
        self.frame = 0
        self.done = False

    @property
    def position(self):
        # NOTE: The way this is written assumes a consistent & stable framerate
        if self.done or (self.frame + 1) == len(self.frames):
            self.done = True
            return self.end
        pos = self.frames[self.frame]
        self.frame = self.frame + 1
        return pos
