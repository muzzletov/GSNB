# GSNB

SCREENSHOT

GSNB is a notebook style interface to the SageMath CAS (sagemath.org) similar to Jupyter but written in Python and Gtk+. It's currently not stable and likely has a lot of bugs. It's also lacking many features that Jupyter supports like 3D plots, tab-autocomplete, function references, pretty printing, LaTeX support, ... Markdown cells support only the most basic functions (paragraphs and headers).

That said it's still usable and - in my opinion - enjoyable. So as you might not want to consider this for production use yet you can still play around with it and maybe file any issues you encounter here on Github. I'm really happy about any feedback I get, be it about code architecture, design, bugs, feature suggestion, ... Even better of course if you want to help with development: I will definately work on and maintain this project for the foreseeable future and review your contributions ASAP, so we can faster "create a viable free open source alternative to Magma, Maple, Mathematica and Matlab."

## Installation on Debian (Ubuntu?)

I'm developing GSNB on Debian and that's what I exclusively tested it with. Installing on Ubuntu should probably work exactly the same.

1. Run the following command to install prerequisite Debian packages:
`apt-get install sagemath python3-bleach python3-markdown libgtk-3-dev libgtksourceview-3.0-dev`

2. Download und Unpack GSNB from GitHub

3. cd to GSNB folder

4. Running the following command should start GSNB:
`python3 __main__.py`

## Installation on other Linux Distributions

Installation on distributions different from Debian or Ubuntu should work more or less the same (if you have SageMath installed). If you have any trouble please get in touch by opening an issue on GitHub. I consider this a bug and will try to help you / provide instructions for your system ASAP.
