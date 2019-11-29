# TraceLab

[![DOI badge](https://img.shields.io/badge/doi-10.1016/j.bbr.2018.10.030-green.svg)](https://doi.org/10.1016/j.bbr.2018.10.030) 

TraceLab is an experiment program designed to study motor control and learning — specifically, learning to execute a motor skill via physical practice or motor imagery based practice.

![tracelab_animation](tracelab_heart.gif)

The task requires participants to execute complex multi-joint upper limb movements by reproducing a series of shapes on a touchscreen. Learning in this task is defined by comparing participant performance on randomly generated shapes versus a repeating shape. The use of randomly generated movements throughout the experiment allows for some control over confounding factors that may influence changes in performance besides learning. The program also includes the ability to include a control task involving perceptual observation of shapes but with no movement task.

Instructions on how to install, run, and export data from TraceLab are provided below.

## Requirements

TraceLab is programmed in Python 2.7 (3.4+ compatible) using the [KLibs framework](https://github.com/a-hurst/klibs). It has been developed and tested on macOS (10.9 through 10.14) and lightly tested on Windows 10, but should also work with minimal hassle on computers running [Ubuntu](https://www.ubuntu.com/download/desktop) or [Debian](https://www.debian.org/distrib/) Linux.

TraceLab was originally designed to run on a 24-inch touchscreen (specificaly, a [Planar PCT2485](https://www.amazon.com/Planar-PCT2485-Widescreen-Multi-Touch-Monitor/dp/B00DFB8KRQ)) at a resolution of 1920x1080. However, TraceLab should work on any touchscreen monitor provided that it has a high enough resolution (larger than 1024x768), and that the TraceLab R analysis scripts have been modified to plot data properly at the screen's resolution. 

## Getting Started

### Prerequisites

In order to install TraceLab, we first need to install some prerequisite libraries that it depends on. These can be easily installed on macOS or Windows using the **pip** Python package manager (replace `pip` with `pip3` if using Python 3):

```bash
pip install git+https://github.com/a-hurst/klibs.git
pip install -U git+https://github.com/a-hurst/py-sdl2.git@sdl2dll
pip install -U git+https://github.com/a-hurst/pysdl2-dll.git@master
```

You will need to have [Git](https://git-scm.com/downloads) installed in order for the above commands to work. If you are using a Mac and already have Xcode or Homebrew installed, you already have Git.

On Linux systems you can ignore the last two pysdl2 lines, but you will need to install the SDL2, SDL2-mixer, and SDL2-ttf libraries using your distro's package manager.

### Installation

Once this has finished, you can then download and install TraceLab with the following commands (replacing `~/Downloads` with the path to the folder where you would like to install TraceLab):

```bash
cd ~/Downloads
git clone https://github.com/LBRF/TraceLab.git
cd TraceLab
```

### Running TraceLab

TraceLab is a KLibs experiment, meaning that it is run using the `klibs` command at the terminal (running the 'experiment.py' file using `python` directly will not work, and will print a warning).

To run the experiment, navigate to the TraceLab folder in Terminal and run `klibs run [screensize]`,
replacing `[screensize]` with the diagonal size of your display in inches (e.g. `klibs run 24` for a 24-inch monitor). If you just want to test the program out for yourself and skip demographics collection, you can add the `-d` flag to the end of the command to launch the experiment in development mode.


### Figure Generation

In TraceLab, some presented figures are randomly generated at the onset of the trial, whereas some figures are loaded from pre-generated **figure templates** and are identical in shape across trials. TraceLab comes with a set of pre-generated templates in the `ExpAssets/Resources/figures` directory, but you can generate your own templates using **capture figures mode**.

To enter capture figures mode, simply set the parameter `capture_figures_mode` to `True` in the experiment's parameters file (`ExpAssets/Config/TraceLab_params.py`) and launch TraceLab normally. You will be guided through the process of generating and saving your own template figures by the on-screen instructions.

To add template figures you have generated to your TraceLab study, just add the names of the desired template files (minus the ".zip" suffix) to either the "figure_name" factor in the experiment's `_independent_variables.py` file, or add them to a custom figure set defined in the `figure_sets.py` file.


## Exporting Data

The data recorded by TraceLab can be split into two groups: **figure & tracing data**, and **participant & trial data**. Various scripts for importing, joining, and analyzing both groups of data can be found in the [TraceLabR](https://github.com/LBRF/TraceLabR/) repository.

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
`.tlfx` | A text file containing the (x, y) pixel coordinates for each frame of the trial figure, as if rendered at a duration of 5 seconds.
`.tlt` | A text file containing the (x, y) pixel coordinates and timestamps for each sample of a recorded response tracing for a physical trial.

Additionally, the file name for each trial's `.zip` contains the (p)articipant id number, (s)ession number, (b)lock number, (t)rial number and date for the trial. For example, `p1_s2_b1_t3_2018-11-30.zip` would contain the data for block 1, trial 3 of session 2 (recorded on November 30, 2018) for the participant whose database ID is 1.

### Participant & Trial Data

Apart from figures and figure tracings, all data collected in TraceLab is neatly organized in an SQL database. To export this data from TraceLab, simply run

```
klibs export -c 
```

while in the TraceLab directory. This will export the trial data from all participants into a single tab-delimited `TraceLab_all_trials.txt` file in the project's `ExpAssets/Data` subfolder.

Alternatively, if you just run `klibs export` without the `-c`, the trial data will be exported into individual tab-delimited text files for each participant.