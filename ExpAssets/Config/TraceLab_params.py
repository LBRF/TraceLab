# TraceLab Param overrides
#
# Any param that is commented out by default is either deprecated or else not yet implemented--don't uncomment or use

#########################################
# Available Hardware
#########################################
eye_tracker_available = False
eye_tracking = False
labjack_available = False
labjacking = False

#########################################
# Environment Aesthetic Defaults
#########################################
default_fill_color = (0, 0, 0, 255)
default_color = (255, 255, 255, 255)
default_response_color = default_color
default_input_color = default_color
default_font_size = 16
default_font_name = 'Frutiger'
default_timeout_message = "Too slow!"

#########################################
# Experiment Structure
#########################################
multi_session_project = True
collect_demographics = True
manual_demographics_collection = True
run_practice_blocks = False
trials_per_block = 20
trials_per_practice_block = 0
blocks_per_experiment = 5
practice_blocks_per_experiment = 0
trials_per_participant = 0
pre_render_block_messages = False
show_practice_messages = True
table_defaults = {'participants': [('sessions_completed', 0), ('condition', "NA")]}
figures = ["heart", "template_1477090164.31", "template_1477106073.55", "template_1477081781.44", "template_1477111169.26", "template_1477121315.85"]
origin_wait_time = 1000  # ms
demo_mode = False
mirror_mode = False
next_trial_message = "Tap here to continue."
experiment_complete_message = "Thanks for participating. You're all finished. Hit any key or tap the screen to exit."
intertrial_rest_interval = 20  # seconds
enable_learned_figures_querying = True


########################################
# Practice Controls
########################################
enable_practice = True
truncate_practice_animation = False
practice_instructions = "The following is a demonstration period. Use this time to learn and then practice the task.\nTap the screen to continue."
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
dm_always_show_cursor = False
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
origin_red_on_code = 1.0
origin_green_on_code = 3.0
origin_off_code = 5.0


########################################
# tlf Controls
########################################
gen_tlfx = False  # extended (5s) interpolation
gen_tlfs = True  # segments file
gen_tlfp = True  # points file
gen_png = True   # image file
gen_ext_png = False  # image file from extended interpolation