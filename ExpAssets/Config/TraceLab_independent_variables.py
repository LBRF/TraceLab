from klibs.KLStructure import FactorSet


# Initialize names and levels of experiment factors

# NOTE: If figure sets are enabled in params.py, the levels of the figure_name
# factor will be ignored in favour of the values in the chosen sets

exp_factors = FactorSet({
    "animate_time": [500, 1000, 1500, 2000, 2500],
    "figure_name": ["random", "template_31"],
})
