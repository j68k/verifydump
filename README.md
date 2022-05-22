# verifydump

verifydump is a command-line tool for verifying that compressed disc images in .chd or .rvz format correctly match those in the [Datfiles produced by the Redump disc preservation project](http://redump.org/downloads/).

The reason it's useful is that the Redump Datfiles describe the uncompressed disc image files (usually in .bin/.cue or .iso format) but it's generally more pleasant for users to store their disc images in .chd/.rvz format because those formats offer excellent compression while still being directly usable in many emulators without the need to decompress the whole file first.

verifydump works by converting the compressed .chd/.rvz file into the original format used by Redump, tweaking the converted dump to match the Redump conventions, and then verifying that it matches the Datfile.

## Required Tools

To convert the disc images between formats verifydump uses third-party tools.

To verify .chd files you need both of:
- chdman, which is made by and [distributed with MAME](https://www.mamedev.org/release.html)
- [binmerge](https://github.com/putnam/binmerge/releases)

To verify .rvz files you need:
- DolphinTool, which is made by and [distributed with Dolphin](https://dolphin-emu.org/download/)

The tools must be available in your system's PATH so that verifydump can find them.

## Installation

You can download a .exe of verifydump for Windows on the [releases](https://github.com/j68k/verifydump/releases) page. The program is written in Python so on Linux or macOS you can install it using [pipx](https://pypa.github.io/pipx/) with:
```Shell
pipx install verifydump
```
or using any other method you like for installing Python packages.

## Usage

To verify your dumps you need to supply verifydump with the Datfile and the compressed files that it should verify. The Datfile (which can be zipped) should be specified first, followed by one or more compressed dump files or folders that contain the dump files:
```Shell
verifydump "Example - SystemName - Datfile (3902) (2022-01-01 01-02-03).zip" "C:\Games\SystemName"
```

If everything is successful, after a little while you'll see output like this:
```
Datfile loaded successfully with 3902 games
Dump verified correct and complete: "Some Game (Disc 1)"
Dump verified correct and complete: "Some Game (Disc 2)"
Dump verified correct and complete: "Other Game"
Dump verified correct and complete: "Best Game"
Successfully verified 4 dumps
```

If any dump can't be successfully verified then you'll see output about what failed after all the other dumps have been checked. The program stops checking a dump after it finds an error, so the error reported might just be the first problem in a file. verifydump never modifies your files, so fixing problems like wrong filenames is up to you.

There are a few options you can use, which can see documentation about by running `verifydump --help`. The `--verbose` option can be helpful if you get an unexpected result, because it makes the program show much more detailed output about exactly what it is doing. Another important option is `--extra-cue-source`, which is described in the following section.

## The problem with .cue files

As mentioned above, verifydump works by converting your compressed disc images into the original format used by Redump. For CD images, that will be .bin/.cue format. There can be a problem, however, which is that the original Redump .cue files sometimes contain extra metadata about the disc that isn't representable in the .chd format. That means that when verifydump converts the .chd, the converted .cue is missing that metadata. It therefore doesn't match the .cue file described in the Datfile and can't be verified. If that happens, you'll see output like this:
```
"Some Game (Disc 1)" .bin files verified and complete, but .cue does not match Datfile
You can either supply the original .cue file yourself using the '--extra-cue-source' option so that we can check that the generated .cue file's essential structure is correct, or ignore .cue file errors with the '--allow-cue-file-mismatches' option
```

As mentioned in that output, the solution to this problem is that you can provide the original .cue file. verifydump can then check that the provided .cue does match the Datfile, and then it can check the converted .cue against the provided one, while ignoring any metadata that isn't supported in the .chd format. That way, it can verify that the essential parts of the converted .cue are correct.

The good news is that Redump makes the .cue files for all systems easily available on [their downloads page](http://redump.org/downloads/) in the Cuesheets column. So if you do encounter this issue, you just need to download the Cuesheets .zip for the system you're verifying, and tell verifydump where to find that file using the `--extra-cue-source` option. You'll then see output like this:
```
Dump .bin files verified correct and complete, and .cue essential structure matches: "Some Game (Disc 1)"
```
which is a slightly long-winded way of saying everything is great.

## Avoiding SSD wear from temporary files

Because verifydump uses external tools to do its conversions, it necessarily creates temporary files for the converted files, and then promptly deletes them after verification. That's a bit unfortunate, because the lifetime of an SSD is limited by the amount of data that's written to it, so it's somewhat wasteful to write big files and then delete them again immediately.

**It's probably not worth worrying about this if you're just going to verify your game collection occasionally**, but if you'll be verifying it very frequently, or if you have a huge collection then it might be worth using a [RAM drive](https://en.wikipedia.org/wiki/RAM_drive) to store the temporary files, so that they don't need to be written to your SSD.

On Windows I've had success using [OSFMount](https://www.osforensics.com/tools/mount-disk-images.html) to mount a new RAM drive with the drive letter T:, and then in the PowerShell terminal that I run verifydump in, setting the TEMP environment variable with `$Env:TEMP="T:\"`. The RAM drive needs to be large enough to fit double the uncompressed size of the largest dump that you will verify, so ~1.5GB is good for CD images, or ~20GB for DVD images.

## Bugs/questions

Please report any bugs or ask any questions by opening an [issue on the project's GitHub](https://github.com/j68k/verifydump/issues). Please assign an appropriate label to your issue to keep things organized.

## Contributing/future work

Pull requests for bug fixes are very welcome, of course. If you're thinking of doing substantial work on a new feature then please open a new issue to discuss it first so we can make sure that we're on the same page about the proposed feature/design.

There may be some [open issues for proposed new features](https://github.com/j68k/verifydump/labels/enhancement) already, and please feel free to star those issues to indicate which ones should be prioritized.

One feature that probably won't be added is support for other compressed image formats, unless they have clear advantages over the ones that are supported now. I'd prefer to nudge users towards whatever the best format is for a given system rather supporting every format just because it's possible.

Thank you very much for reading everything, and I hope you like the tool!
