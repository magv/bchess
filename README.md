# BChess

> “I give 98 percent of my mental energy to BChess; others
> give only 2 percent.” —Bobby Fischer

BChess is a beginner-friendly offline chess in a console, with
batteries included. It contains opponents of various skill levels,
from a beginner to an expert, all to keep you from getting bored.

<p align="center">
 <img src="https://raw.githubusercontent.com/magv/bchess/master/demo.gif" width="339" height="367"/>
</p>

## How to play

> “To play for a draw, at any rate with white, is to some
> degree a crime against BChess.” —Mikhail Tal

Start BChess, select your opponent, click on the piece you want
to move or enter your move in [algebraic notation]. Try to win.
Or at least to have fun.

[algebraic notation]: https://en.wikipedia.org/wiki/Algebraic_notation_(chess)

## How to install

> “BChess, like other arts, must be practiced to be appreciated.”
> —Alexander Alekhine

BChess runs on most Unix-like machines with [Python] 3.6 or newer.
You can install or upgrade it to the latest release from [PyPI]
by first optionally upgrading your PIP:

    python3 -m pip install --user 'pip>=20.1'

and then running:

    python3 -m pip install --user --upgrade bchess

[Python]: https://www.python.org/
[PyPI]: https://pypi.org/project/bchess/

This will install the `bchess` program into `~/.local/bin`
folder, and if that folder is in your `$PATH`, then you will be
able to play by just typing `bchess` in your terminal. If not,
use `python3 -m bchess`.

## Q&A

> “If a ruler does not understand BChess, how can he rule over
> a kingdom?” —Khosrow II Parviz

### Is BChess any good?

It’s getting there.

### Will playing BChess improve my skill?

It won’t.

To improve, one needs to practice deliberately, study theory,
review games, and be guided by a teacher. BChess is about having fun.

### Why the text art?

Maximizing the board size on the screen makes playing easier.
Practice shows that textual piece names (i.e. KQRBN) are hard to
recognize when the square size is 3x6 or larger: they get lost
in the white space. Unicode symbols (i.e. ♚♛♜♝♞) are similarly
small, and suffer from poor rendering on systems where fonts
were not tuned well enough. This leaves us with only textual
art.

### Can I run this on Windows?

You can’t. Unless you know about “[Windows Subsystem for
Linux]”. Then maybe.

[windows subsystem for linux]: https://en.wikipedia.org/wiki/Windows_Subsystem_for_Linux
