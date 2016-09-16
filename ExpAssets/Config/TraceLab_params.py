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
# EyeLink Sensitivities
#########################################
saccadic_velocity_threshold = 20
saccadic_acceleration_threshold = 5000
saccadic_motion_threshold = 0.15

fixation_size = 1 # deg of visual angle
box_size = 1 # deg of visual angle
cue_size = 1 # deg of visual angle
cue_back_size = 1 # deg of visual angle

#########################################
# Experiment Structure
#########################################
multi_session_project = True
collect_demographics = True
run_practice_blocks = False
trials_per_block = 50
trials_per_practice_block = 0
blocks_per_experiment = 1
practice_blocks_per_experiment = 0
trials_per_participant = 0
pre_render_block_messages = False
show_practice_messages = True
table_defaults = {'participants': [('sessions_completed', 0), ('condition', "NA")]}
figures = ["testfig"]
origin_wait_time = 1000  # ms
demo_mode = False
mirror_mode = False

#########################################
# Development Mode Settings
#########################################
dm_suppress_debug_pane = False
dm_auto_threshold = True


# For everything involving color,  http://www.colorspire.com/rgb-color-wheel/ will let you get the rgb values
# for any color you prefer

########################################
#  Dot Controls
########################################
tracker_dot_size = 5  # diameter in px
tracker_dot_perimeter =  2  # px; *additional* to tracking dot size, so the diameter gets 2 x this number larger

tracker_dot_color = (255, 0, 0)  # r, g, b, and the last value should always be 255
tracker_dot_perimeter_color = (255, 255, 255)

origin_size = 30  # px

########################################
# Feedback Controls
########################################
response_feedback_color = (0,0,255)
stimulus_feedback_color = (255, 0, 0)
max_feedback_time = 500  # ms
ignore_points_at = []  # list of (x,y) coordinates to be removed
trial_error_msg = "Trial ended too soon!"

########################################
# Button Bar Controls
########################################
button_count = 5
button_size = 75  # px square
button_screen_margins = 300  # margins on either side of screen where buttons cant be placed
y_offset = 300  # how far down the screen, vertically, the buttons should be placed
button_instructions = "How many times did the dot change course {0}?"  #  the {0} will contain the direction text

########################################
# Figure Controls
########################################
generation_timeout = 10  # seconds
capture_figures_mode = False

generate_quadrant_intersections = True

outer_margin_v = 150
outer_margin_h = 100
inner_margin_v = 100
inner_margin_h = 100
# trace_mode = False

# inner_margin = 300 #todo: v + h for inner margins
avg_seg_per_f = (9, 2)  # (avg number, variance)
avg_seg_per_q = (2, 1)  # (avg number, variance)
angularity = 0.5  # 0 = all curves, 1 = all lines

# line controls
min_linear_acuteness = 0.1  # must be between 0 and 1; low vals advised, higher vals increasingly get impossible to draw

# curve controls
slope_magnitude = (0.25, 0.75)  # 0 = a straight line (ie. no curve), 1 = an infinitely steep curve (hint: don't pick this ;)
peak_shift = (0.0, 0.5)  # 0 == perfect symmetry (ie. bell curve) and 1 == a right  triangle
curve_sheer = (0.0, 0.5)  # this is hard to describe, but 1 is again an impossible value, and this will grow to lunacy fast
path_length = -1  # length (px); -1 ignores this parameter; path length will override seg_length params if they conflict
seg_report_fuzz = (2, 4)
# seg_count_fuzz_width
# seg_answer_pos

 # NOTE VARIABLE SESSION COUNTS

########################################
# Practice Controls
########################################
show_practice_demo = True
practice_instructions = "The following is a demonstration period. Use this time to learn and then practice the task.\nTap the screen to continue."
play_narration = False  # toggles the audio component