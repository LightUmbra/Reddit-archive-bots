# Reddit archive bots


This repository contains python scripts for two different reddit bots. It also includes instructions for using them. Both should work on Windows and Linux. They may work on Mac as well, but I can't test it on a Mac.

The first, archive_bot.py, makes archives of links in submissions in [archive.org](https://web.archive.org/), [archive.is](http://archive.is/), and [removeddit.com](http://removeddit.com/) for Reddit links and just archive.org and archive.is for non-Reddit links.

The second, outline_bot.py, makes links to [Outline.com](https://outline.com/) for links in a submission. Outline.com is a site that tries to make sites more readable by removing ads, images, and other potential clutter. Since Outline.com does not work well on many sites, the script is set to ignore certain URLs or file extensions. More sites can be added to the ignore list.

These bots require Python 3.6 or above. They may work on lower versions of Python 3, but I can't easily test or debug on them, so I can't easily help if it doesn't work. They also require up to date versions of [pip](https://pypi.org/project/pip/), [PRAW](https://praw.readthedocs.io/en/latest/), and [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/?). Instructions on how to install these are included in the instructions.txt file.

I will try to keep these up to date, but if they stop working start an issue here or send me a message on reddit at [/u/LightUmbra](https://www.reddit.com/message/compose?to=/u/LightUmbra).

Most of this code was taken from justcool393's great bot [SnapshillBot](https://github.com/justcool393/SnapshillBot). I made changes so it works off local text files, is more suited for one single sub, and is easier for people to implement themselves.