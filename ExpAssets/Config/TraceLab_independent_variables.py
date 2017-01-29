__author__ = 'jono'
from klibs.KLIndependentVariable import IndependentVariableSet, IndependentVariable

TraceLab_ind_vars = IndependentVariableSet()

TraceLab_ind_vars.add_variable("animate_time", int)
TraceLab_ind_vars.add_variable("figure_name", str)

TraceLab_ind_vars['animate_time'].add_values(500, 1000, 1500, 2000, 2500)
TraceLab_ind_vars['figure_name'].add_values("random", "template_1477090164.31")