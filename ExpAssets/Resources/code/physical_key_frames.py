__author__ = 'jono'
import abc
import time
import imp, sys, shutil, os
from KeyFrames import *

instructions = "You are about to see a white dot trace out a movement on the screen.\n /" \
			   "All movements begin and end at the same point.\n /" \
			   "You will later be asked to repeat this movement yourself on the touchscreen.\n /" \
			   "This tutorial will show you how to respond."
kf1 = KeyFrame(500, True, True)

