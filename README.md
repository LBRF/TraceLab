# TraceLab

[![DOI badge](https://img.shields.io/badge/doi-10.1016/j.bbr.2018.10.030-green.svg)](https://doi.org/10.1016/j.bbr.2018.10.030)

TraceLab is an experiment program designed to study motor control and learning — specifically, how complex motor skills are learned via physical practice or motor imagery.

![tracelab_animation](tracelab_heart.gif)

The task requires participants to execute complex multi-joint upper limb movements by reproducing a series of shapes on a touchscreen. Learning in this task is defined by comparing participant performance on randomly generated shapes versus a repeating shape. The use of randomly generated movements throughout the experiment allows for some control over confounding factors that may influence changes in performance besides learning. The program also includes the ability to include a control task involving perceptual observation of shapes but with no movement task.

Instructions on how to install, run, and export data from TraceLab are provided below.


## Requirements

This study requires the following hardware to work as intended:

* A computer with Python 3.9 or later installed
* A touchscreen monitor

However, the task will still run without a touchscreen (in development mode or with `force_show_cursor` set to True in params.py) for testing and demonstration purposes.


## Getting Started

This TraceLab experiment is written in Python 3 (3.9+ compatible) using the [KLibs framework](https://github.com/a-hurst/klibs). It should install and run on any recent version of macOS, Linux, or Windows.


### Installing Dependencies

#### Option 1: Self-Contained Environment

To install all of the task's Python dependencies in a self-contained virtual environment, run the following commands in a terminal window inside the same folder as this README:

```bash
pip install uv
uv sync
```
These commands should create a fresh environment for the TraceLab project with all its dependencies installed inside it. Note that to run commands using this environment, you will need to prefix them with `uv run`, e.g. `uv run klibs run 24`.

#### Option 2: Global Installation

Alternatively, to install the dependencies for the task in your global Python environment, run the following commands in a terminal window:

```bash
pip install https://github.com/a-hurst/klibs/releases/download/0.7.8b2/klibs-0.7.8b2.tar.gz
```

### Running TraceLab

TraceLab is a KLibs experiment, meaning that it is run using the `klibs` command at the terminal (running the 'experiment.py' file using `python` directly will not work, and will print a warning).

To run the experiment, navigate to the TraceLab folder in Terminal and run `klibs run [screensize]`,
replacing `[screensize]` with the diagonal size of your display in inches (e.g. `klibs run 24` for a 24-inch monitor). If you just want to test the program out for yourself and skip demographics collection, you can add the `-d` flag to the end of the command to launch the experiment in development mode.


### Figure Generation

In TraceLab, some presented figures are randomly generated at the onset of the trial, whereas some figures are loaded from pre-generated **figure templates** and are identical in shape across trials. TraceLab comes with a set of pre-generated templates in the `ExpAssets/Resources/figures` directory, but you can generate your own templates using **capture figures mode**.

To enter capture figures mode, simply set the parameter `capture_figures_mode` to `True` in the experiment's parameters file (`ExpAssets/Config/TraceLab_params.py`) and launch TraceLab normally. You will be guided through the process of generating and saving your own template figures by the on-screen instructions.

To add template figures you have generated to your TraceLab study, just add the names of the new template(s) to either the "figure_name" factor in the experiment's `independent_variables.py` file, or add them to a figure set in `params.py`.


## Exporting Data

The data recorded by TraceLab can be split into two groups: **figure & tracing data**, and **participant & trial data**. Various scripts for importing, joining, and analyzing both groups of data can be found in the [TraceLabAnalysis](https://github.com/LBRF/TraceLabAnalysis/) repository.

### Figure and Tracing Data

Figure and tracing data is stored separately from other data in TraceLab. In the experiment's `ExpAssets/Data/` folder, each participant has a separate folder containing their figure data, identified by participant id and the date/time the id was initialized (e.g. `p9_2019-11-11_19-54`).

Each participant tracing folder contains a separate folder for each session of the task (e.g. `session_1/`, `session_2/`), with each session folder containing `.zip` files with the figure data from each trial of that session.

```
.
├── ...
├── p1_2018-11-28_14-37
│   ├── session_1
│   │   ├── p1_s1_b1_t1_2018-11-28.zip
│   │   ├── p1_s1_b1_t2_2018-11-28.zip
│   │   ├── p1_s1_b1_t3_2018-11-28.zip
│   │   └── ...
│   └── session_2
│       ├── p1_s2_b1_t1_2018-11-30.zip
│       ├── p1_s2_b1_t2_2018-11-30.zip
│       ├── p1_s2_b1_t3_2018-11-30.zip
│       └── ...
├── p2_2018-11-29_10-54
|   └── ...
└── ...
```
Each trial's `.zip` file contains data files with the following suffixes:

File | Description
--- | ---
`preview.png` | An image of the fully-interpolated figure shown on the trial
`.tlf` | A text file containing the (x, y) pixel coordinates and timestamps for each frame of the figure animated on the trial.
`.tlfp` | A text file containing the (x, y) pixel coordinates of the vertices of the figure animated on the trial.
`.tlfs` | A text file containing the (x, y) pixel coordinates of the start/end/control points for each segment of the figure animated on the trial.
`.tlt` | A text file containing the (x, y) pixel coordinates and timestamps for each sample of a recorded tracing response (physical trials only).

Additionally, the file name for each trial's `.zip` contains the (p)articipant id number, (s)ession number, (b)lock number, (t)rial number and date for the trial. For example, `p1_s2_b1_t3_2018-11-30.zip` would contain the data for block 1, trial 3 of session 2 (recorded on November 30, 2018) for the participant whose database ID is 1.

### Participant & Trial Data

Apart from figures and figure tracings, all data collected in TraceLab is neatly organized in an SQL database. To export this data from TraceLab, simply run

```
klibs export
```

while in the TraceLab directory. This will export the trial data from all participants into individual tab-delimited text files for each participant in the project's `ExpAssets/Data` subfolder.

Data from any participants that did not complete all of their sessions will be saved to the `ExpAssets/Data/incomplete` folder.


