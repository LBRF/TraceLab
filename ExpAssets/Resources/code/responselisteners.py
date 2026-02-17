import aggdraw
import numpy as np
import klibs.KLParams as P
from klibs.KLTime import precise_time
from klibs.KLBoundary import Boundary
from klibs.KLUserInterface import mouse_pos
from klibs.KLResponseListeners import BaseResponseListener
from klibs.KLGraphics.utils import rgb_to_rgba, aggdraw_to_array


class DrawingListener(BaseResponseListener):
    """A custom class for collecting drawing responses.

    Args:
        min_duration (float, optional): The minimum duration (in seconds) of the
            drawing, to prevent premature/accidental response ends. Defaults to
            0.25 seconds.
        timeout (float, optional): The maximum duration (in seconds) to wait for a
            valid response. Defaults to None (no timeout).
        loop_callback (callable, optional): An optional function or method to be
            called every time the collection loop checks for new input.

    """
    def __init__(self, min_duration=0.25, timeout=None, loop_callback=None):
        super(DrawingListener, self).__init__(timeout, loop_callback)
        self.origin_boundary = None
        self.min_duration = min_duration
        # Runtime
        self.points = []
        self._origin_touched = None
        self._drawing_start = None

    def _timestamp(self):
        # NOTE: precise_time seems to be more consistent than time.perf_counter here
        # for some reason even though it should theoretically be identical.
        return precise_time()

    def set_origin(self, origin):
        """Sets the boundary to use for the origin point of the drawing.

        Args:
            origin (:obj:`~klibs.KLBoundary.Boundary`): The boundary to use for
                the start/end point of the drawing.

        """
        if not isinstance(origin, Boundary):
            e = "'origin' must be a valid Boundary object."
            raise TypeError(e)
        self.origin_boundary = origin

    def collect(self):
        """Collects a drawing response from the participant.

        drawing: A list of x/y coordinates (in pixels) and their corresponding
            timestamps (in seconds) relative to drawing start representing the
            trajectory and timecourse of the drawing. Each sample is formatted
            as `(x, y, timestamp)`.
        rt: Reaction time, defined as the interval between response collection
            start and the participant touching the origin.
        it: Initiation time, defined as the interval between the participant
            touching the origin and the start of the actual drawing.
        mt: Movement time, defined as the interval between the start of the
            drawing and the end of the drawing (return to origin).

        Returns:
            tuple: A ``(drawing, rt, it, mt)`` tuple containing the drawing trajectory
            and its reaction time, initiation time, and movement time.

        """
        return super(DrawingListener, self).collect()

    def init(self):
        """Initializes the listener for response collection.

        """
        if not self.origin_boundary:
            e = "Origin point must be set before collecting a drawing response."
            raise RuntimeError(e)
        self._loop_start = self._timestamp()

    def listen(self, q):
        """Updates the state of the drawing based on cursor movements.

        Args:
            q (list): A list of input events. Unused for this listener.

        Returns:
            tuple or None: A ``(drawing, rt, it, mt)`` tuple if a complete draw
            response been made, otherwise None.

        """
        loc = mouse_pos()
        timestamp = self._timestamp()

        # If response not initiated, check if cursor is within origin and start if so
        if not self.started:
            if loc in self.origin_boundary:
                self._origin_touched = timestamp

        # If within origin after drawing start, end drawing if min duration has elapsed
        elif self._drawing_start and loc in self.origin_boundary:
            last_timestamp = self.points[-1][-1]
            if last_timestamp > self.min_duration and len(self.points) >= 2:
                rt = round(self._origin_touched - self._loop_start, 4)
                it = round(self._drawing_start - self._origin_touched, 4)
                mt = round(self.points[-1][2], 4)
                return (self.points, rt, it, mt)

        # Once response is initiated and cursor leaves origin, start recording drawing
        if self.started and not loc in self.origin_boundary:
            if not self._drawing_start:
                self._drawing_start = timestamp
                p = (loc[0], loc[1], 0.0)
            else:
                p = (loc[0], loc[1], round(timestamp - self._drawing_start, 7))
            self.points.append(p)

        return None

    def cleanup(self):
        """Resets the listener state after a response has been collected.

        """
        self.points = []
        self._loop_start = None
        self._origin_touched = None
        self._drawing_start = None

    @property
    def started(self):
        """bool: True if the tracing has been initiated, otherwise False.

        """
        return self._origin_touched != None

    @property
    def draw_time(self):
        """float: The time elapsed since the start of the actual drawing.

        """
        if not self._drawing_start:
            return 0.0
        return self._timestamp() - self._drawing_start



class DrawSurface(object):
    """An optimized class for rendering live tracings.

    To avoid the need to create a new surface and re-render the whole tracing every
    frame, this class creates a single surface and updates it with new tracing data
    as it comes in.

    Necessary to avoid dropped frames when tracing feedback is enabled.

    """
    def __init__(self, size, color, thickness=1):
        # Create pen for drawing
        color = rgb_to_rgba(color)
        self._pen = aggdraw.Pen(color[:3], thickness, color[3])
        # Create reusable drawing surface
        self.surf = aggdraw.Draw("RGBA", P.screen_x_y, (0, 0, 0, 0))
        self.surf.setantialias(True)
        self._raw = None # surface bytes, empty until rendered

    def update(self, points):
        # Adds the line between the last two points to the surface
        if len(points) >= 2:
            p1 = "M{0},{1}".format(*points[-2][:2])
            p2 = "L{0},{1}".format(*points[-1][:2])
            self.surf.symbol((0, 0), aggdraw.Symbol(p1 + p2), self._pen)

    def render(self):
        # Get the raw RGBA bytes from the drawing surface
        self._raw = self.surf.tobytes()
        # Cast the raw bytes directly to a blittable numpy array
        arr = np.frombuffer(self._raw, dtype=np.uint8)
        return arr.reshape(self.surf.size[1], self.surf.size[0], 4)
