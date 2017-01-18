from os.path import exists, join

from klibs import P
from klibs.KLNamedObject import NamedObject, NamedInventory
from klibs.KLUtilities import iterable
from klibs.KLGraphics import fill, blit, flip
from klibs.KLCommunication import message
from klibs.KLUserInterface import any_key

class FigureSet(NamedObject):

	def __init__(self, name):
		self.figures = []
		super(FigureSet, self).__init__(name)

	def __parse_values__(self):
		for v in self.figures:
			if iterable(v):
				self.figures.append(list(v))
			else:
				self.figures.append([v,1])

	def add_figure(self, figure_name):
		if iterable(figure_name):
			self.figures.append(list(figure_name))
		else:
			self.figures.append([figure_name, 1])

	def add_figures(self, *figures):
		for f in figures:
			self.add_figure(f)

	def confirm_figure(self, figure_name):
		if not exists(join(P.resources_dir, "figures", figure_name+".zip")):
			fill()
			e_msg = "One or more figures listed in the figure set '{0}' weren't found.\n " \
					"Please check for errors and try again. TraceLab will now exit.".format(self.name)
			message(e_msg, location=P.screen_c, registration=5, flip_screen=True)
			any_key()
			self.quit()

