# TraceLab parameter overrides

#########################################
# Runtime Settings
#########################################
collect_demographics = True
manual_demographics_collection = True
run_practice_blocks = False

demo_mode = False
mirror_mode = False
enable_learned_figures_querying = True

#########################################
# Available Hardware
#########################################
eye_tracking = False
eye_tracker_available = False
labjack_available = True
magstim_available = True
magstim_serial_port = '/dev/cu.UEBOOM2-LWACP-7'

#########################################
# Environment Aesthetic Defaults
#########################################
default_fill_color = (0, 0, 0, 255)
default_color = (255, 255, 255, 255)
default_font_size = 16
default_font_name = 'Frutiger'

next_trial_message = "Tap here to continue."
experiment_complete_message = "Thanks for participating! You're all finished. Hit any key or tap the screen to exit."

#########################################
# Experiment Structure
#########################################
multi_session_project = True
trials_per_block = 20
blocks_per_experiment = 5
table_defaults = {'participants': [('sessions_completed', 0), ('condition', "NA")]}

final_condition = 'physical' # condition for last block or session (if multi-session)
origin_wait_time = 1000  # ms
figure_load_time = 4 # seconds
tms_pulse_delay = 100 # ms, time between trial end and sending of TMS trigger

########################################
# Practice Controls
########################################
enable_practice = True
truncate_practice_animation = False
practice_instructions = "The following is a demonstration period. Use this time to learn and then practice the task.\n\nTap the screen to continue."
play_narration = True  # toggles the audio component
practice_figure = "heart"
practice_animation_time = 3500 # ms
bubble_location = (1550, 275)

#########################################
# Development Mode Settings
#########################################
dm_suppress_debug_pane = False
dm_auto_threshold = True
dm_override_practice = False  # only for testing on a monitor which is too small to support practice animations
dm_render_progress = False  # if true, user's attempts to draw the figure will always be rendered
dm_setup_only = False
dm_ignore_local_overrides = True
dm_always_show_cursor = True
use_log_file = False
# For everything involving color,  http://www.colorspire.com/rgb-color-wheel/ will let you get the rgb values
# for any color you prefer

########################################
#  Dot Controls
########################################
tracker_dot_size = 5  # diameter in px
tracker_dot_perimeter = 4  # px; *additional* to tracking dot size, so the diameter gets 2 x this number larger
tracker_dot_color = (0, 0, 0)  # r, g, b, and the last value should always be 255
tracker_dot_perimeter_color = (255, 255, 255)
origin_size = 50  # px

########################################
# Feedback Controls
########################################
response_feedback_color = (0,255,255)
stimulus_feedback_color = (211, 211, 211)
max_feedback_time = 2000  # ms
ignore_points_at = [(1919,1079),(119,1079)]  # list of (x,y) coordinates to be removed
trial_error_msg = "Oops! Something went wrong. Let's try that again later."

########################################
# Button Bar Controls
########################################
btn_count = 5
btn_size = 75  # px square
btn_s_pad = 450  # margins on either side of screen where buttons cant be placed
y_pad = 300  # how far down the screen, vertically, the buttons should be placed
btn_instrux = "How many times did the dot change course {0}?"  #  the {0} will contain the direction text

########################################
# Figure Controls
########################################
figures = [ # pre-generated figures to use
    "heart",
    "template_1477090164.31",
    "template_1477106073.55",
    "template_1477081781.44",
    "template_1477111169.26",
    "template_1477121315.85"
]

generation_timeout = 10  # seconds
capture_figures_mode = False
auto_generate = True
auto_generate_count = 2  # when auto_generate and capture_figures_mode are true, this many figures will be generated

generate_quadrant_intersections = True
outer_margin_v = 50
outer_margin_h = 50
inner_margin_v = 10
inner_margin_h = 10
# trace_mode = False

# inner_margin = 300 #
avg_seg_per_f = (4, 2)  # (avg number, variance)
avg_seg_per_q = (2, 1)  # (avg number, variance)
angularity = 0  # 0 = all curves, 1 = all lines

# line controls
min_linear_acuteness = 0.1  # must be between 0 and 1; low vals advised, higher vals increasingly get impossible to draw

# curve controls
slope_magnitude = (0.25, 0.5)  # 0 = a straight line (ie. no curve), 1 = an infinitely steep curve (hint: don't pick this ;)
peak_shift = (0.25, 0.5)  # 0 == perfect symmetry (ie. bell curve) and 1 == a right  triangle
curve_sheer = (0.1, 0.3)  # this is hard to describe, but 1 is again an impossible value, and this will grow to lunacy fast
path_length = -1  # length (px); -1 ignores this parameter; path length will override seg_length params if they conflict
seg_report_fuzz = (2, 4)

########################################
# Labjack Codes
########################################
trigger_codes = {
    "tms_trigger": 255
}

########################################
# tlf Controls
########################################
gen_tlfx = False  # extended (5s) interpolation
gen_tlfs = True  # segments file
gen_tlfp = True  # points file
gen_png = True   # image file
gen_ext_png = False  # image file from extended interpolation

#########################################
# Data Export Settings
#########################################
primary_table = "trials"
unique_identifier = "user_id"
exclude_data_cols = ['klibs_commit', 'created', 'session_count', 'sessions_completed', 'initialized']