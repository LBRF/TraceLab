__author__ = 'jono'
from klibs.KLNamedObject import NamedInventory
from FigureSet import FigureSet

"""
##########################
#       READ ME 	     #
##########################
	Originally we were going to use one document per figure-set; now this single document contains all of them.
	So first here's the walk-through on how to make a *single* figure set:

##########################
# CREATING A FIGURE SET  #
##########################
	To create a figure set, just assign a new FigureSet() object to a variable, and populate it's name argument.

												***IMPORTANT***
	The variable name you choose to create the figure set is completely immaterial and will never again be relevant to
	the experiment. It is the name you give the figure set when you create it that's important; this is what you'll
	type when setting up a new participant. So, in the following exmample:

>> new_set = FigureSet("MyFavoriteFigures)

	"MyFavorteFigures" is the name of the figure set, NOT new_set.

	Then arbitrarily add figures to that set. You can do this in two ways, either en mass or one at a time; they're
	identical, it's just up to you whichever you find cleaner.

	So for single-figure adding, following from the example above:

>> new_set.add_figure("figure_name")

	Which implicitly assumes a weighting of 1, or put another way is equivalent to:

>> new_set.add_figure(["figure_name", 1])

	Which then sort of suggests how different weight values should be added, ie:

>> new_set.add_figure(["figure_name", 4])

	To do this as a group, you simply use the add_figures() method instead, like so:

>> new_set.add_figures("figure_name_1", "figure_name_2", ["figure_name_3, 4])

	Note that the last item in the add_figures() example has an explicit weight; so do the first two values, it's
	just redundant to weight them as 1 each time.

##########################
#  GROUPING FIGURE SETS  #
##########################
	The final step is really easy; you just need to ensure you add each created FigureSet to the variable
	trace_lab_figure_sets like so:

>> trace_lab_figure_sets.add(new_set)
>> trace_lab_figure_sets.add(new_set_the_second)
>> trace_lab_figure_sets.add(new_set_the_second_etc)

	or just overwrite the original variable as a standard python list:

>> trace_lab_figure_sets = [new_set, new_set_the_second, new_set_the_second_etc]

	Below is a real-world example that should actually run, provided the figures listed actually exist in your 
	figures directory

"""


# create the figure sets
fig_set_1 = FigureSet("test")
fig_set_1.add_figures(("heart",2), "template_1477081781.44")

fig_set_2 = FigureSet("test1")
fig_set_2.add_figures("heart", "template_1477090164.31")

fig_set_3 = FigureSet("test2")
fig_set_3.add_figures(("heart",3), "template_1477090164.31")

fig_set_4 = FigureSet("test3")
fig_set_4.add_figures(("heart",3), "template_1477090164.31")

