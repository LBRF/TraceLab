# TraceLab parameter overrides

from klibs import P

#########################################
# Runtime Settings
#########################################
collect_demographics = True
manual_demographics_collection = True
manual_trial_generation = True
run_practice_blocks = False

demo_mode = False
mirror_mode = False
enable_learned_figures_querying = True

capture_figures_mode = False
auto_generate = False  # whether to generate figures without prompting in capture mode
auto_generate_count = 10  # number of figures to generate in auto-generate/capture mode

#########################################
# Available Hardware
#########################################
eye_tracking = False
eye_tracker_available = False
labjack_available = False

#########################################
# Environment Aesthetic Defaults
#########################################
default_fill_color = (0, 0, 0, 255)
default_color = (255, 255, 255, 255)
default_font_size = 18
default_font_name = 'Hind-Medium'

next_trial_message = "Tap here to continue."
experiment_complete_message = (
    "Thanks for participating! "
    "You're all finished. Hit any key or tap the screen to exit."
)

#########################################
# Experiment Structure
#########################################
multi_session_project = True
trials_per_block = 20
conditions = []
default_condition = None
table_defaults = {}

origin_wait_time = 3.0  # seconds

########################################
# Practice Controls
########################################
enable_practice = True
practice_instructions = (
    "The following is a demonstration period. Use this time to learn and then practice the task."
    "\n\nTap the screen to continue."
)
practice_figure = "heart"
practice_animation_time = 3500 # ms
bubble_location = (1550, 275)

#########################################
# Development Mode Settings
#########################################
dm_auto_threshold = True
dm_render_progress = False  # if True, drawing feedback will always be shown in devmode
dm_ignore_local_overrides = False
dm_always_show_cursor = True
use_log_file = False  # Not sure this is terribly useful

########################################
# Dot Controls
########################################
dot_size = 5  # diameter in px
dot_stroke = 4  # width of stroke around tracker dot in px
dot_color = (255, 255, 255)  # r, g, b
dot_stroke_col = (255, 255, 255)
origin_size = 50  # px

########################################
# Feedback Controls
########################################
response_feedback_color = (0, 255, 255)
stimulus_feedback_color = (211, 211, 211)
feedback_duration = 2000  # ms
ignore_points_at = [(1919,1079),(119,1079),(239,1079)]  # list of (x,y) coordinates to be removed

########################################
# Button Bar Controls
########################################
btn_count = 5
btn_size = 75  # px square
btn_s_pad = 450  # margins on either side of screen where buttons can't be placed
y_pad = 300  # how far down the screen, vertically, the buttons should be placed
control_q = "How many times did the dot change course {0}?"  # the {0} will contain the direction

########################################
# Figure Controls
########################################
generation_timeout = 0.5  # seconds

generate_quadrant_intersections = True  # Not quite sure what this does
outer_margin_v = 50  # minimum vertical distance figure points can be from screen margins (in px)
outer_margin_h = 50  # minimum horizontal distance figure points can be from screen margins (in px)
inner_margin_v = 10  # minimum vertical distance figure points can be from screen center (in px)
inner_margin_h = 10  # minimum horizontal distance figure points can be from screen center (in px)
curve_margin_v = 10  # minimum distance from vertical screen margins for curve segments (in px)
curve_margin_h = 10  # minimum distance from horizontal screen margins for curve segments (in px)

avg_seg_per_f = (4, 2)  # (avg, variance) for number of segments per figure
avg_seg_per_q = (2, 1)  # (avg, variance) for number of segments per quadrant
angularity = 0  # 0 = all curves, 1 = all lines

# line controls
min_linear_acuteness = 0.1  # must be between 0 and 1; low vals advised, higher vals increasingly get impossible to draw

# curve controls
slope_magnitude = (0.25, 0.5)  # 0 = a straight line (ie. no curve), 1 = an infinitely steep curve (hint: don't pick this ;)
peak_shift = (0.25, 0.5)  # 0 == perfect symmetry (ie. bell curve) and 1 == a right  triangle
curve_sheer = (0.1, 0.3)  # this is hard to describe, but 1 is again an impossible value, and this will grow to lunacy fast

########################################
# Labjack Codes
########################################
trigger_codes = {}

########################################
# tlf Controls
########################################
gen_tlfx = True  # extended (5s) interpolation
gen_tlfs = True  # segments file
gen_tlfp = True  # points file
gen_png = True   # image file
gen_ext_png = False  # image file from extended interpolation

#########################################
# Data Export Settings
#########################################
primary_table = "trials"
unique_identifier = "user_id"
exclude_data_cols = [
    'klibs_commit', 'created', 'session_count', 'sessions_completed', 'initialized'
]

#########################################
# Session & Block Structures
#########################################
# NOTE: session structures are specified as a list of lists of strings,
# with the number of lists defining the number of sessions for that
# condition, the number of strings within each list defining the number
# of blocks within that session, and the strings defining the trial type
# and feedback type for each block, in the format "type-feedback":
#
# Trial types:
#  - "PP" (physical tracing response)
#  - "MI" (motor imagery response)
#  - "CC" (control / motion direction judgement response)
#
# Feedback types:
#  - "X" / "XX"  (no feedback)
#  - "R" / "XR"  (live tracing feedback during tracing response)
#  - "V" / "VX"  (presentation of target figure with tracing overlay after response made)
#  - "VR"        (both "R" and "V")
#
# If a project has more than one session structure, a prompt will appear after creating a
# new study ID asking which structure to use for that participant. This choice will be
# remembered across sessions for that user. If only one session structure is given,
# it will automatically be used for each participant without prompting.
session_structures = {
    'a': [
        ['MI-XX', 'MI-XX', 'MI-XX', 'MI-XX', 'PP-XX'] # session 1
    ]
}
