# TraceLab

TraceLab is an experiment program designed to test fine motor control through the tracing of shapes [this should be improved, mostly here for placeholder].

## Requirements

TraceLab is programmed in Python 2.7 using the [KLibs framework](https://github.com/a-hurst/klibs). It has been developed and tested on macOS (10.9 through 10.13), but should also work with minimal hassle on computers running [Ubuntu](https://www.ubuntu.com/download/desktop) or [Debian](https://www.debian.org/distrib/) Linux. 

TraceLab is not directly compatible with any version of Windows, nor will it run under the [Windows Subsystem for Linux](https://msdn.microsoft.com/en-us/commandline/wsl/install_guide).

TraceLab was originally designed to run on a 24-inch touchscreen (specificaly, a [Planar PCT2485](https://www.amazon.com/Planar-PCT2485-Widescreen-Multi-Touch-Monitor/dp/B00DFB8KRQ)) at a resolution of 1920x1080. Although preliminary efforts have been made to make TraceLab resolution independent, some stimuli still do not scale properly when run at different resolutions, and data collection on other touch screens at different resolutions have not yet been tested. At present, we only recommend collecting data using a 1080p touchscreen.

## Getting Started

### Prerequisites

In order to install TraceLab, we first need to install some prerequisite libraries that it depends on. These can be easily installed on macOS using the [Homebrew](https://brew.sh) package manager. Once Homebrew has been installed, you can install all the required libraries by entering the following line at the command prompt:

```
brew install sdl2 sdl2_ttf sdl2_mixer portaudio
```
You will also need the **pip** package manager to install the rest of TraceLab's prerequisites. If it isn't installed already, you can install it by running `sudo easy_install pip`.

### Installation

Once this has finished, you can then download and install TraceLab with the following commands (replacing `~/Downloads` with the path to the folder where you would like to install TraceLab):

```
cd ~/Downloads
git clone https://github.com/LBRF/TraceLab.git
cd TraceLab
sudo -H pip install -r requirements.txt
```

### Using TraceLab

TraceLab is a KLibs experiment, meaning that it is run using the `klibs` command at the terminal (running the 'experiment.py' file using python directly will not work, and will print a warning).

To run the experiment, navigate to the TraceLab folder in Terminal and run `klibs run [screensize]`,
replacing `[screensize]` with the diagonal size of your display in inches (e.g. `klibs run 24` for a 24-inch monitor). If you just want to test the program out for yourself and skip demographics collection, you can add the `-d` flag to the end of the command to launch the experiment in development mode.

To export data you've collected using TraceLab to a single file, run `klibs export -c` while in the TraceLab directory. The participant and trial data will be exported to a tab-delimited text file found at `TraceLab/ExpAssets/Data/TraceLab_all_trials.txt`.
