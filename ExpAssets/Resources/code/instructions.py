import os
import sdl2.sdlmixer as mixer
from sdl2.ext import cursor_hidden

from klibs import P
from klibs.KLUtilities import scale
from klibs.KLTime import CountDown
from klibs.KLEventQueue import pump, flush
from klibs.KLUserInterface import any_key, key_pressed, hide_cursor, show_cursor
from klibs.KLGraphics import fill, flip, blit, NumpySurface
from klibs.KLGraphics import KLDraw as kld
from klibs.KLCommunication import message
from klibs.KLAudio import AudioClip

from animations import Keyframe, Animation


IMAGE_ASSETS = [
    "pointer.png",
    "pointer_sml.png",
    "arrow_up.png",
    "arrow_down.png",
    "arrow_right.png",
    "arrow_left.png",
    "dotted_line.png",
    "dotted_curve.png",
    "thought_bubble.png",
    "not_recording.png",
]

AUDIO_FILES = {
    'physical': ["PP1", "PP2", "PP3", "PP4", "PP5", "PP6"],
    'imagery': ["MI1", "MI2", "MI3", "MI4", "MI5", "PP6"],
    'control': ["CC1", "CC2", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "CC9"],
}

STIM_LOCS = {
    "origin": (960, 780),
    "shape_p1": (480, 360),
    "shape_p2": (960, 360),
    "shape_c2": (720, 120),
    "shape_p3": (1440, 360),
    "shape_c3": (1200, 120),
    "text_low": (960, 680), # P.screen_y / 0.63
    "text_midlow": (960, 580), # P.screen_y / 0.54
    "pointer_start": (1070, 900),
    "pointer_pre_origin": (960, 770),
    "pointer_leaves": (920, 750),
    "pointer_near_end": (1050, 710),
    "pointer_miss": (860, 800),
    "not_recording": (960, 340),
    # MI
    "thought_bubble": (1550, 275),
    "mi_origin": (1550, 375),
    "mi_shape_p1": (1400, 200),
    "mi_shape_p2": (1550, 200),
    "mi_shape_c2": (1475, 130),
    "mi_shape_p3": (1700, 200),
    "mi_shape_c3": (1625, 130),
    "pointer_lifted": (920, 740),
    # CC
    "text_top": (960, 150),
    "cc_pointer_start": (960, 1080),
}

ANIMATIONS = {
    'shape1': [0.90, ('origin', 'shape_p1')],
    'shape2': [0.78, ('shape_p1', 'shape_p2', 'shape_c2')],
    'shape3': [0.78, ('shape_p2', 'shape_p3', 'shape_c3')],
    'shape4': [0.90, ('shape_p3', 'origin')],
    'pointer_begin': [1.0, ('pointer_start', 'pointer_pre_origin')],
    'pointer_click': [0.2, ('pointer_pre_origin', 'origin')],
    'pointer_leaves': [0.5, ('origin', 'pointer_leaves')],
    # PP-specific animations
    'pointer_to_p1': [0.9, ('pointer_leaves', 'shape_p1')],
    'pointer_nears_end': [0.9, ('shape_p3', 'pointer_near_end')],
    'pointer_return': [0.5, ('pointer_near_end', 'origin')],
    'pointer_miss': [0.5, ('pointer_near_end', 'pointer_miss')],
    'pointer_recover': [0.5, ('pointer_miss', 'origin')],
    # MI-specific animations
    'mi_shape1': [0.90, ('mi_origin', 'mi_shape_p1')],
    'mi_shape2': [0.78, ('mi_shape_p1', 'mi_shape_p2', 'mi_shape_c2')],
    'mi_shape3': [0.78, ('mi_shape_p2', 'mi_shape_p3', 'mi_shape_c3')],
    'mi_shape4': [0.90, ('mi_shape_p3', 'mi_origin')],
    'pointer_lifted': [0.2, ('pointer_leaves', 'pointer_lifted')],
    # CC-specific animations
    'shape1_slow': [2.2, ('origin', 'shape_p1')],
    'shape2_slow': [1.2, ('shape_p1', 'shape_p2', 'shape_c2')],
    'shape3_slow': [1.2, ('shape_p2', 'shape_p3', 'shape_c3')],
    'shape4_slow': [1.2, ('shape_p3', 'origin')],
}


class SkipException(Exception):
    # Special exception to allow easy skipping of instructions
    pass


def skip_instructions():
    # Pause any audio clips currently playing and raise exception
    mixer.Mix_HaltChannel(-1)
    raise SkipException('skipping instructions')


def get_demo_resources(condition):
    # Load in and scale instruction images
    images = {}
    for img_file in IMAGE_ASSETS:
        img_path = os.path.join(P.image_dir, img_file)
        img_name = img_file.split(".")[0]
        # Load image and scale to the screen
        img = NumpySurface(img_path)
        scaled_width = int(img.width * (P.screen_x / 1920.0))
        images[img_name] = img.scale(width=scaled_width)

    # Load in audio instructions for the current condition
    audio = {}
    for clip_name in AUDIO_FILES[condition]:
        audio_path = os.path.join(P.audio_dir, clip_name + ".mp3")
        audio[clip_name] = AudioClip(audio_path)

    # Pre-scale stim locations from 1920x1080
    locs = {}
    for name, loc in STIM_LOCS.items():
        locs[name] = scale(loc, (1920, 1080))

    # Pre-generate animations from specified durations/paths
    anims = {}
    for name, anim in ANIMATIONS.items():
        duration, path = anim
        start = locs[path[0]]
        end = locs[path[1]]
        ctrl = locs[path[2]] if len(path) == 3 else None
        anims[name] = Animation(start, end, ctrl, duration)

    return (images, audio, locs, anims)


def run_animations(anims, stim_set=[], audio=None):

    # If an audio clip was provided, start playing if it isn't playing already
    if audio and not audio.playing:
        audio.play()

    # Run each given animation/keyframe in sequence
    for keyframe in anims:
        # If keyframe has 3 elements, middle element is custom blit registration
        if len(keyframe) == 3:
            stim, a_reg, a = keyframe
        else:
            stim, a = keyframe
            a_reg = 5
        
        # Run animation until complete, drawing any background stimuli
        a.reset()
        while not a.done:
            fill()

            # Draw background stimuli
            for x in stim_set:
                # If background stimulus has blit() method, use that to draw it
                if hasattr(x, 'blit'):
                    x.blit()
                else:
                    # If stim has 3 elements, middle item is blit registration
                    if len(x) == 3:
                        s, reg, loc = x
                    else:
                        s, loc = x
                        reg = 5
                    blit(s, reg, loc)
            
            # Draw animated stimulus (if any) at its current position
            if stim is None:
                # Still need to increment timer on empty keyframe
                a.position
            else:
                blit(stim, a_reg, a.position)

            # Redraw the scren and check for any keyboard input
            flip()
            if key_pressed('delete'):
                skip_instructions()


def show_demo_screen(
        msg=" ", stim_set=[], duration=None, msg_y=None, audio=None
    ):
    """Draws text and stimuli onto the screen for task instructions."""

    msg_x = int(P.screen_x / 2)
    msg_y = int(P.screen_y * 0.5) if msg_y is None else msg_y
    txt = message(msg, align="center")

    # If an audio clip was provided, start playing if it isn't playing already
    if audio and not audio.playing:
        audio.play()
    
    # Draw text/stimuli to the screen for given duration (or until audio done)
    t = CountDown(duration) if duration else None
    while (t.counting() if duration else audio.playing):
        fill()
        blit(txt, 5, (msg_x, msg_y))
        for stim, loc in stim_set:
            if isinstance(loc, Animation):
                blit(stim, 5, loc.position)
            else:
                blit(stim, 5, loc)
        flip()
        if key_pressed('delete'):
            skip_instructions()


def task_demo_pp(exp):

    # Initialize task stimuli for the demo
    images, voiceover, locs, anims = get_demo_resources('physical')
    white_dot = exp.tracker_dot
    origin_red = exp.origin_inactive
    origin_green = exp.origin_active
    txt_low = locs['text_low'][1]

    # Show initial set of instructions and wait for them to touch the screen
    show_demo_screen(
        ("You are about to see a white dot trace out a movement on the screen.\n"
         "All movements begin and end at the same point.\n\n"
         "You will later be asked to repeat this movement yourself on the touchscreen.\n"
         "This tutorial will show you how to respond.\n\n"
         "When you tap the touchscreen to continue, the movement will begin."),
        audio=voiceover["PP1"]
    )

    # Show an example of what the figure animation looks like
    run_animations([
        (white_dot, Keyframe(locs['origin'], duration=0.5)),
        (white_dot, anims['shape1']),
        (white_dot, anims['shape2']),
        (white_dot, anims['shape3']),
        (white_dot, anims['shape4']),
        (origin_red, Keyframe(locs['origin'], duration=0.5)),
    ])

    # Explain basics of task, show hand pointer moving to origin
    show_demo_screen(
        ("The red circle indicates that you are now able to respond.\n"
         "Note that this is not a reaction time test - you do not need to respond "
         "right away; take your time!"),
        [(origin_red, locs['origin'])], audio=voiceover["PP2"], msg_y=txt_low
    )
    run_animations([
        (images['pointer'], Keyframe(locs['pointer_start'], duration=0.3)),
        (images['pointer'], anims['pointer_begin'])
    ],
        stim_set=[(origin_red, locs['origin'])]
    )

    # Illustrate the hand pointer touching origin to initiate the trial
    background_stim = [
        (message("Once you touch the circle..."), locs["text_low"]),
        (origin_red, locs['origin'])
    ]
    run_animations([
        (images['pointer'], Keyframe(locs['pointer_pre_origin'], duration=0.5)),
        (images['pointer'], anims['pointer_click']),
        (images['pointer'], Keyframe(locs['origin'], duration=1.0)),
    ],
        stim_set=background_stim, audio=voiceover["PP3"]
    )
    show_demo_screen(
        "...and begin to move...", 
        stim_set=[
            (origin_red, locs['origin']),
            (images['pointer'], anims['pointer_leaves'])
        ],
        audio=voiceover["PP4"], duration=2.1, msg_y=txt_low
    )

    # Show the hand pointer tracing the figure, stopping before touching origin
    show_demo_screen(
        ("...the circle will turn green, indicating that the computer is now "
         "recording.\nYour job is to trace out exactly the movement you observed, "
         "matching the speed."),
        stim_set=[
            (origin_green, locs['origin']),
            (images['pointer'], locs['pointer_leaves'])
        ],
        duration=5.6, msg_y=txt_low
    )
    run_animations([
        (images['pointer'], anims['pointer_to_p1']),
        (images['pointer'], anims['shape2']),
        (images['pointer'], anims['shape3']),
        (images['pointer'], anims['pointer_nears_end']),
    ],
        stim_set=[(origin_green, locs['origin'])]
    )

    # Illustrate what it looks like to successfully end a trial
    pp_instr_6 = (
        "The trial ends when you return to the starting point. If successful, the "
        "green dot will disappear.\nIf still green, simply drag your finger onto "
        "the circle again.\nIf still red, it didn't record, so just try again."
    )
    instructions_6 = (message(pp_instr_6, align='center'), P.screen_c)
    show_demo_screen(
        stim_set=[
            instructions_6,
            (origin_green, locs['origin']),
            (images['pointer'], locs['pointer_near_end'])
        ],
        duration=4.4, audio=voiceover["PP5"]
    )
    run_animations(
        # Show hand pointer returning to origin
        [(images['pointer'], anims['pointer_return'])],
        stim_set=[(origin_green, locs['origin']), instructions_6]
    )
    run_animations(
        # Show origin disappearing after pointer touches it
        [(images['pointer'], Keyframe(locs['origin'], duration=1.0))],
        stim_set=[instructions_6]
    )

    # Illustrate what it looks like to accidentally miss the origin and how to
    # correct for this if it happens
    run_animations([
        (images['pointer'], anims['pointer_miss']),
        (images['pointer'], Keyframe(locs['pointer_miss'], duration=1.0)),
        (images['pointer'], anims['pointer_recover']),
        (images['pointer'], Keyframe(locs['origin'], duration=0.5)),
    ],
        stim_set=[(origin_green, locs['origin']), instructions_6]
    )
    run_animations(
        # Show origin disappearing after pointer eventually touches it
        [(images['pointer'], Keyframe(locs['origin'], duration=1.4))],
        stim_set=[instructions_6]
    )

    # Illustrate what it looks like if the trial didn't start successfully
    run_animations(
        [(images['pointer'], anims['pointer_return'])],
        stim_set=[(origin_red, locs['origin']), instructions_6]
    )
    run_animations([
        # Flash the 'not recording' image at the top of the screen
        (images['not_recording'], Keyframe(locs['not_recording'], duration=0.5)),
        (None, Keyframe(None, duration=0.5)),
        (images['not_recording'], Keyframe(locs['not_recording'], duration=0.5)),
        (None, Keyframe(None, duration=0.5)),
        (images['not_recording'], Keyframe(locs['not_recording'], duration=0.5)),
    ], stim_set=[
        instructions_6,
        (origin_red, locs['origin']),
        (images['pointer'], locs['origin']),
    ])

    # Show final screen of instructions
    show_demo_screen(
        "Now it's your turn. Try some practice.",
        audio=voiceover["PP6"], duration=3.0
    )


def task_demo_mi(exp):

    # Initialize task stimuli for the demo
    images, voiceover, locs, anims = get_demo_resources('imagery')
    white_dot = exp.tracker_dot
    origin_red = exp.origin_inactive
    origin_green = exp.origin_active
    thought_bubble = (images['thought_bubble'], locs['thought_bubble'])
    txt_midlow = locs['text_midlow'][1]

    # Show initial set of instructions and wait for them to touch the screen
    show_demo_screen(
        ("You are about to see a white dot trace out a movement on the screen.\n"
         "All movements begin and end at the same point.\n\n"
         "You will later be asked to repeat this movement using motor imagery.\n"
         "This means you will practice the movement mentally, without actually "
         "performing the movement.\n\nWe want you to imagine what it would look "
         "like for you to perform the movement,\nand also how it would feel. "
         "This tutorial will show you how to respond.\n\n"
         "When you tap the touchscreen to continue, the movement will begin."),
        audio=voiceover["MI1"]
    )

    # Show an example of what the figure animation looks like
    run_animations([
        (white_dot, Keyframe(locs['origin'], duration=0.5)),
        (white_dot, anims['shape1']),
        (white_dot, anims['shape2']),
        (white_dot, anims['shape3']),
        (white_dot, anims['shape4']),
        (origin_red, Keyframe(locs['origin'], duration=0.5)),
    ])

    # Explain basics of task, show hand pointer moving to origin
    show_demo_screen(
        ("The red circle indicates that you are now able to respond.\n"
         "Note that this is not a reaction time test; you do not need to respond "
         "right away\nTake your time!"),
        [(origin_red, locs['origin'])], audio=voiceover["MI2"], msg_y=txt_midlow
    )
    run_animations([
        (images['pointer'], Keyframe(locs['pointer_start'], duration=0.3)),
        (images['pointer'], anims['pointer_begin'])
    ],
        stim_set=[(origin_red, locs['origin'])]
    )

    # Illustrate the hand pointer touching origin to initiate the trial
    background_stim = [
        (message("Once you touch the red circle..."), locs['text_midlow']),
        (origin_red, locs['origin'])
    ]
    run_animations([
        # last one is 0.8s for MI?
        (images['pointer'], Keyframe(locs['pointer_pre_origin'], duration=0.5)),
        (images['pointer'], anims['pointer_click']),
        (images['pointer'], Keyframe(locs['origin'], duration=1.0)),
    ],
        stim_set=background_stim, audio=voiceover["MI3"]
    )

    # Illustrate origin turning green once touched
    show_demo_screen(
        stim_set=[
            (origin_red, locs['origin']),
            (images['pointer'], anims['pointer_leaves'])
        ],
        audio=voiceover["MI4"], duration=1.4, msg_y=txt_midlow
    )

    # Show the hand pointer tracing the figure, stopping before touching origin
    pointer_during_mi = (images['pointer'], locs['pointer_leaves'])
    show_demo_screen(
        ("...and begin to move, the circle will turn green,\n"
         "indicating that the computer is now recording."),
        stim_set=[(origin_green, locs['origin']), pointer_during_mi],
        duration=4.1, msg_y=txt_midlow
    )

    # Illustrate performing a trial using motor imagery
    mi_instr_5 = (
        "Stop moving, and perform the movement mentally.\n\n"
        "Remember: do not actually perform the movement physically.\n"
        "Just imagine the movement, visualizing what it would look like for "
        "you to do it, and how it would feel."
    )
    background_stim = [
        (message(mi_instr_5, align='center'), locs['text_midlow']),
        (origin_green, locs['origin']),
        pointer_during_mi,
    ]
    show_demo_screen(stim_set=background_stim, duration=0.7)
    run_animations([
        (None, Keyframe(None, duration=0.5)),
        (images['pointer_sml'], Keyframe(locs['mi_origin'], duration=0.5)),
        (images['pointer_sml'], anims['mi_shape1']),
        (images['pointer_sml'], anims['mi_shape2']),
        (images['pointer_sml'], anims['mi_shape3']),
        (images['pointer_sml'], Keyframe(locs['mi_shape_p3'], duration=8.7)),
        (images['pointer_sml'], anims['mi_shape4']),
        (images['pointer_sml'], Keyframe(locs['mi_origin'], duration=2.6)),
    ],
        stim_set = background_stim + [thought_bubble]
    )

    # Illustrate lifting finger off origin to end the trial
    show_demo_screen(
        ("When you imagine returning to the starting point - the green circle - "
         "lift your finger from the screen."),
        stim_set=[
            (origin_green, locs['origin']),
            (images['pointer'], anims['pointer_lifted']),
        ],
        duration=1.8, msg_y=txt_midlow
    )
    mi_instr_7 = (
        "This indicates that the trial is over, and the green dot will disappear.\n"
        "Remember, you must try to match the movement AND the speed that you observed."
    )
    run_animations([
        (origin_green, Keyframe(locs['origin'], duration=3.5)),
        (None, Keyframe(None, duration=4.5)),
    ],
        stim_set = [(message(mi_instr_7, align='center'), locs['text_midlow'])],
        audio=voiceover["MI5"]
    )

    # Show final screen of instructions
    show_demo_screen(
        "Now it's your turn. Try some practice.",
        audio=voiceover["PP6"], duration=3.0
    )


def task_demo_cc(exp):

    # Initialize task stimuli for the demo
    images, voiceover, locs, anims = get_demo_resources('control')
    white_dot = exp.tracker_dot
    button_box = exp.control_bar
    buttons = button_box.buttons
    finish_button = button_box.finish_b
    target_circle = kld.Annulus(50, thickness=4, fill=(255, 0, 0))
    txt_top = locs['text_top'][1]

    # Generate button bar animations using positions from button bar
    dx, dy = scale((15, 15), (1920, 1080), center=False)
    button2_loc = (buttons[1].location[0] + dx, buttons[1].location[1] + dy)
    button2_loc_pressed = (button2_loc[0], button2_loc[1] + 10)
    button3_loc = (buttons[2].location[0] + dx, buttons[2].location[1] + dy)
    button3_loc_pressed = (button3_loc[0], button3_loc[1] + 10)
    finish_loc = (finish_button.location[0] + dx, finish_button.location[1] + dy)
    finish_loc_pressed = (finish_loc[0], finish_loc[1] + 10)
    anims['to_button_2'] = Animation(
        locs['cc_pointer_start'], button2_loc, duration=1.0
    )
    anims['press_button_2'] = Animation(
        button2_loc, button2_loc_pressed, duration=0.3
    )
    anims['to_button_3'] = Animation(
        button2_loc_pressed, button3_loc, duration=0.5
    )
    anims['press_button_3'] = Animation(
        button3_loc, button3_loc_pressed, duration=0.3
    )
    anims['to_finish'] = Animation(
        button3_loc_pressed, finish_loc, duration=1.0
    )
    anims['press_finish'] = Animation(
        finish_loc, finish_loc_pressed, duration=0.3
    )

    # Show initial set of instructions
    show_demo_screen(
        ("You are about to see a white dot trace out a movement on the screen.\n"
         "When you tap the touchscreen to continue, the movement will begin.\n\n"
         "All movements begin and end at the same point.\n\n"
         "For example..."),
        audio=voiceover["CC1"]
    )

    # Show an example of what the figure animation looks like
    run_animations([
        (white_dot, Keyframe(locs['origin'], duration=0.5)),
        (white_dot, anims['shape1']),
        (white_dot, anims['shape2']),
        (white_dot, anims['shape3']),
        (white_dot, anims['shape4']),
        (white_dot, Keyframe(locs['origin'], duration=0.5)),
    ])

    # Begin explaining how the dot "bounces" between locations during movements
    cc_instr_2 = (
        "All movements in this experiment will hit five corners, including the "
        "starting point.\nLooking more closely, you'll see that the movement "
        "appears to bounce from each corner."
    )
    instructions_2 = (message(cc_instr_2, align='center'), locs['text_top'])
    run_animations([
        (white_dot, Keyframe(locs['origin'], duration=1.0)),
        (white_dot, anims['shape1_slow']),
    ],
        stim_set=[instructions_2], audio=voiceover["CC2"]
    )
    run_animations([
        (target_circle, Keyframe(locs['shape_p1'], duration=1.3)),
        (target_circle, Keyframe(locs['origin'], duration=1.3)),
    ],
        stim_set=[instructions_2, (white_dot, locs['shape_p1'])]
    )

    # Continue explaining/illustrating how the dot "bounces" between locations
    cc_instr_3 = (
        "Looking more closely, you'll see that the movement appears to bounce "
        "from each corner."
    )
    instructions_3 = (message(cc_instr_3, align='center'), locs['text_top'])
    run_animations([
        (white_dot, Keyframe(locs['shape_p1'], duration=2.2)),
        (white_dot, anims['shape2_slow']),
        (white_dot, Keyframe(locs['shape_p2'], duration=2.0)),
    ],
        stim_set=[instructions_3]
    )

    # Explain what participants need to pay attention to during the movement
    show_demo_screen(
        ("After each movement, you will be asked how many times the dot moved in "
         "a certain direction after hitting a corner.\n"
         "In other words, which way did it bounce?"),
        stim_set=[(white_dot, locs['shape_p2'])],
        duration=10.8, audio=voiceover["CC3"], msg_y=txt_top
    )

    # Illustrate what it looks like for the dot to bounce up and right
    run_animations(
        [(white_dot, anims['shape3_slow'])], audio=voiceover["CC4"]
    )
    cc_instr_5 = "The dot moves UP and RIGHT from the corner."
    run_animations([
        (images['arrow_up'], 2, Keyframe(locs['shape_p2'], duration=0.7)),
        (images['arrow_right'], 4, Keyframe(locs['shape_p2'], duration=0.7)),
    ],
        stim_set=[
            (message(cc_instr_5), locs['text_top']),
            (white_dot, locs['shape_p3']),
            (images['dotted_curve'], 1, locs['shape_p2'])
    ])
    run_animations(
        [(white_dot, Keyframe(locs['shape_p3'], duration=0.7))],
        stim_set=[(message(cc_instr_5), locs['text_top'])]
    )

    # Illustrate what it looks like for the dot to bounce down and left
    cc_instr_6 = "And then the dot moves DOWN and LEFT from the corner."
    instructions_6 = [message(cc_instr_6), locs['text_top']]
    run_animations(
        [(white_dot, anims['shape4_slow'])],
        stim_set=[instructions_6], audio=voiceover["CC5"]
    )
    run_animations([
        (images['arrow_down'], 8, Keyframe(locs['shape_p3'], duration=0.7)),
        (images['arrow_left'], 6, Keyframe(locs['shape_p3'], duration=0.7)),
    ],
        stim_set=[
            instructions_6,
            (white_dot, locs['origin']),
            (images['dotted_line'], 9, locs['shape_p3'])
    ])
    run_animations(
        [(white_dot, Keyframe(locs['origin'], duration=0.5))],
        stim_set=[instructions_6]
    )

    # Explain the response format for the task
    show_demo_screen(
        ("At the end of each movement, you will be asked:\n"
        "'How many times the dot changed course to the LEFT, RIGHT, UP or DOWN?'\n\n"
        "Pay attention to movements carefully, as you will be asked about one "
        "direction randomly.\nThe movements will happen quickly, so don't worry "
        "about being perfect.\nUse your best judgement."),
        duration=18.6, audio=voiceover["CC6"]
    )

    # Illustrate what it looks like to make a response with the button bar
    cc_instr_8 = (
        "When you're ready, pick a number.\n"
        "The answer will always be a number from one to five.")
    instructions_8 = (message(cc_instr_8, align='center'), locs['text_top'])
    run_animations([
        (None, Keyframe(None, duration=1.0)),
        (images['pointer'], anims['to_button_2']),
        (images['pointer'], Keyframe(button2_loc, duration=0.2)),
        (images['pointer'], anims['press_button_2']),
    ],
        stim_set=[instructions_8, button_box], audio=voiceover["CC7"]
    )
    # Set button 2 to green to indicate it being pressed
    buttons[1].active = True
    finish_button.active = True
    run_animations(
        [(images['pointer'], Keyframe(button2_loc_pressed, duration=2.4))],
        stim_set=[instructions_8, button_box]
    )

    # Illustrate what it looks like to change and finalize a response
    cc_instr_9 = "You can always change your answer before finally confirming it."
    instructions_9 = (message(cc_instr_9, align='center'), locs['text_top'])
    run_animations([
        (images['pointer'], Keyframe(button2_loc_pressed, duration=0.5)),
        (images['pointer'], anims['to_button_3']),
        (images['pointer'], anims['press_button_3']),
    ],
        stim_set=[instructions_9, button_box], audio=voiceover["CC8"]
    )
    buttons[1].active = False
    buttons[2].active = True
    run_animations([
        (images['pointer'], Keyframe(button3_loc_pressed, duration=0.2)),
        (images['pointer'], anims['to_finish']),
        (images['pointer'], Keyframe(finish_loc, duration=0.3)),
        (images['pointer'], anims['press_finish']),
        (images['pointer'], Keyframe(finish_loc_pressed, duration=1.0)),
    ],
        stim_set=[instructions_9, button_box]
    )

    # Show final screen of instructions
    show_demo_screen(
        "Now it's your turn. Try some practice.",
        audio=voiceover["CC9"], duration=3.0
    )


def play_tutorial(exp, trial_type):

    cursor_was_shown = cursor_hidden() == False
    hide_cursor()
    try:
        if trial_type == "physical":
            task_demo_pp(exp)
        elif trial_type == "imagery":
            task_demo_mi(exp)
        elif trial_type == "control":
            task_demo_cc(exp)
        else:
            e = "Unknown trial type '{0}'"
            raise RuntimeError(e.format(trial_type))
    except SkipException:
        # Instructions can be skipped by pressing the delete key
        pass

    # If cursor was visible before tutorial, unhide it after
    if cursor_was_shown:
        show_cursor()
