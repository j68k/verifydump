import logging
import os
import pathlib
import re
import subprocess
import tempfile


class ConversionException(Exception):
    def __init__(self, message: str, converted_file_path: pathlib.Path, tool_output: str = None):
        super().__init__(message)
        self.converted_file_path = converted_file_path
        self.tool_output = tool_output


def convert_chd_to_normalized_redump_dump_folder(chd_path: pathlib.Path, redump_dump_folder: pathlib.Path, system: str, show_command_output: bool):
    """
    Convert a dump file to Redump format in the specified folder.
    """

    cue_file_path = pathlib.Path(redump_dump_folder, chd_path.stem + ".cue")

    if system and system.lower() in ("Sega - Dreamcast".lower(), "dc", "Arcade - Sega - Chihiro".lower(), "chihiro", "Arcade - Sega - Naomi".lower(), "naomi", "Arcade - Sega - Naomi 2".lower(), "naomi2", "Arcade - Namco - Sega - Nintendo - Triforce".lower(), "trf"):
        # These systems use GD-ROM media, which needs special handling. chdman does support GD-ROM dumps, but it only supports converting them to and from .gdi format and not to and from .cue format (it will attempt the conversion to or from .cue format, but the results will not be correct). The Redump Datfiles use .cue format, but we can still use chdman to get the correct .bin files by telling it to convert to .gdi format, because the .bin files are the same for .gdi and .cue format dumps.
        convert_chd_to_bin_gdi(chd_path, cue_file_path.parent, show_command_output)
        # We could then convert the .gdi file to the .cue format that Redump's Datfiles refer to. That would be somewhat involved, though, and I don't think it's worth the effort when users can easily supply the original Redump .cue if they want to, so we actually just discard the .gdi file. We do rename the .bin files to match the Redump conventions, though:
        normalize_redump_bin_gdi_dump(cue_file_path)
    else:
        convert_chd_to_bincue(chd_path, cue_file_path, show_command_output)
        normalize_redump_bincue_dump(cue_file_path)


def convert_chd_to_bincue(chd_file_path: pathlib.Path, output_cue_file_path: pathlib.Path, show_command_output: bool):
    # Use another temporary directory for the chdman output files to keep those separate from the binmerge output files:
    with tempfile.TemporaryDirectory() as chdman_output_folder_path_name:
        chdman_cue_file_path = pathlib.Path(chdman_output_folder_path_name, output_cue_file_path.name)

        logging.debug(f'Converting "{chd_file_path.name}" to .bin/.cue format')
        chdman_result = subprocess.run(["chdman", "extractcd", "--input", str(chd_file_path), "--output", str(chdman_cue_file_path)], stdout=None if show_command_output else subprocess.DEVNULL)
        if chdman_result.returncode != 0:
            # chdman provides useful progress output on stderr so we don't want to capture stderr when running it. That means we can't provide actual error output to the exception, but I can't find a way around that.
            raise ConversionException("Failed to convert .chd using chdman", chd_file_path, None)

        logging.debug(f'Splitting "{output_cue_file_path.name}" to use separate tracks if necessary')
        binmerge_result = subprocess.run(["binmerge", "--split", "-o", str(output_cue_file_path.parent), str(chdman_cue_file_path), chdman_cue_file_path.stem], capture_output=True, text=True)
        if show_command_output:
            print(binmerge_result.stdout, end="")
        if binmerge_result.returncode != 0:
            raise ConversionException("Failed to split .bin into separate tracks using binmerge", chd_file_path, binmerge_result.stdout)


def normalize_redump_bincue_dump(cue_file_path: pathlib.Path):
    dump_path = cue_file_path.parent
    dump_name = cue_file_path.stem

    has_multiple_tracks = len(list(dump_path.glob(f"{dump_name} (Track *).bin"))) > 1
    if not has_multiple_tracks:
        original_bin_name = f"{dump_name} (Track 1).bin"
        single_track_bin_name = f"{dump_name}.bin"

        logging.debug(f'Renaming "{original_bin_name}" to "{single_track_bin_name}" because there is only one .bin file in the dump')

        os.rename(
            pathlib.Path(dump_path, original_bin_name),
            pathlib.Path(dump_path, single_track_bin_name),
        )

        cue_file_path.write_text(cue_file_path.read_text().replace(f'FILE "{original_bin_name}"', f'FILE "{single_track_bin_name}"'), newline="\r\n")

    is_cue_iso_compatible = not has_multiple_tracks and re.match(r'^\s*FILE\s+"' + re.escape(f"{dump_name}.bin") + r'"\s*BINARY\s+TRACK 01 MODE1/2048\s+INDEX 01 00:00:00\s*$', cue_file_path.read_text())
    if is_cue_iso_compatible:
        logging.debug(f'"{cue_file_path.name}" is .iso compatible so converting dump to .iso and discarding .cue')

        single_track_bin_path = pathlib.Path(dump_path, single_track_bin_name)
        iso_file_path = pathlib.Path(dump_path, f"{dump_name}.iso")

        single_track_bin_path.rename(iso_file_path)
        cue_file_path.unlink()


def convert_chd_to_bin_gdi(chd_file_path: pathlib.Path, output_folder_path: pathlib.Path, show_command_output: bool):
    logging.debug(f'Converting "{chd_file_path.name}" to .bin/.gdi format')
    chdman_gdi_file_path = pathlib.Path(output_folder_path, chd_file_path.with_suffix(".gdi").name)
    chdman_result = subprocess.run(["chdman", "extractcd", "--input", str(chd_file_path), "--output", str(chdman_gdi_file_path)], stdout=None if show_command_output else subprocess.DEVNULL)
    if chdman_result.returncode != 0:
        # chdman provides useful progress output on stderr so we don't want to capture stderr when running it. That means we can't provide actual error output to the exception, but I can't find a way around that.
        raise ConversionException("Failed to convert .chd to .bin/.gdi using chdman", chd_file_path, None)


def normalize_redump_bin_gdi_dump(cue_file_path: pathlib.Path):
    game_name = cue_file_path.stem

    bin_and_raw_file_paths = list(cue_file_path.parent.glob(f"{game_name}*.bin")) + list(cue_file_path.parent.glob(f"{game_name}*.raw"))
    redump_bin_filename_format = get_redump_bin_filename_format(game_name, len(bin_and_raw_file_paths))

    track_number_parser = re.compile(f"^{re.escape(game_name)}(?P<track_number>[0-9]+)\\.(?:bin|raw)$")

    for original_bin_or_raw_file_path in bin_and_raw_file_paths:
        track_number_parser_result = track_number_parser.match(original_bin_or_raw_file_path.name)
        if not track_number_parser_result:
            raise ConversionException(".bin/.raw file doesn't match expected filename pattern", original_bin_or_raw_file_path, None)
        track_number = int(track_number_parser_result.group("track_number"))
        redump_bin_filename = redump_bin_filename_format.format(track_number=track_number)
        original_bin_or_raw_file_path.rename(original_bin_or_raw_file_path.with_name(redump_bin_filename))

    # The Datfile includes .cue files rather than .gdi files so convert our .gdi into a .cue:
    gdi_file_path = cue_file_path.with_suffix(".gdi")
    convert_gdi_to_cue(gdi_file_path=gdi_file_path, cue_file_path=cue_file_path)
    gdi_file_path.unlink()


def get_redump_bin_filename_format(game_name: str, number_of_tracks: int) -> str:
    track_number_digits_needed = 2 if number_of_tracks >= 10 else 1
    return game_name + " (Track {track_number:0" + str(track_number_digits_needed) + "d}).bin"


def convert_gdi_to_cue(gdi_file_path: pathlib.Path, cue_file_path: pathlib.Path):
    gdi_track_lines = gdi_file_path.read_text().splitlines()[1:]  # The first line in the file is just the total number of tracks.

    redump_bin_filename_format = get_redump_bin_filename_format(gdi_file_path.stem, len(gdi_track_lines))

    gdi_line_pattern = re.compile(r"^\s*(?P<track_number>[0-9]+)\s+(?P<lba>[0-9]+)\s+(?P<gdi_track_mode>[0-9]+)\s+(?P<sector_size>[0-9]+)\s+(?P<track_filename>\".*?\")\s+(?P<disc_offset>[0-9]+)$")

    with open(cue_file_path, "wt", encoding="utf-8", newline="\r\n") as cue_file:
        for gdi_track_line in gdi_track_lines:
            gdi_track_match = gdi_line_pattern.match(gdi_track_line)

            if gdi_track_match is None:
                raise ConversionException(f"Line in .gdi file didn't match expected format: {gdi_track_line}", gdi_file_path)

            track_number = int(gdi_track_match.group("track_number"))
            lba = int(gdi_track_match.group("lba"))
            gdi_track_mode = int(gdi_track_match.group("gdi_track_mode"))
            sector_size = int(gdi_track_match.group("sector_size"))

            if track_number == 1:
                if lba != 0:
                    raise ConversionException(f"Unexpected LBA of first track: {lba}", gdi_file_path)
                cue_file.write("REM SINGLE-DENSITY AREA\n")

            if track_number == 3:
                if lba != 45000:
                    raise ConversionException(f"Unexpected LBA of track 3: {lba}", gdi_file_path)
                cue_file.write("REM HIGH-DENSITY AREA\n")

            if gdi_track_mode == 0:
                cue_track_mode = "AUDIO"
            elif gdi_track_mode == 4:
                # This isn't a perfect, because a track with .gdi mode 4 and one of these sector sizes could also be a .cue MODE 2 track, but I don't see a way to determine that from the .gdi file:
                if sector_size == 2048 or sector_size == 2352:
                    cue_track_mode = f"MODE1/{sector_size:04d}"
                else:
                    cue_track_mode = f"MODE2/{sector_size:04d}"
            else:
                raise ConversionException(f"Unexpected .gdi track mode: {gdi_track_mode}", gdi_file_path)

            cue_file.write(f'FILE "{redump_bin_filename_format.format(track_number=track_number)}" BINARY\n')
            cue_file.write(f"  TRACK {track_number:02d} {cue_track_mode}\n")
            # The .gdi format apparently doesn't store information about the track pre-gaps, but it does seem that the pattern used on GD-ROM discs is predictable so we can just recreate them with some simple logic:
            if cue_track_mode == "AUDIO":
                cue_file.write("    INDEX 00 00:00:00\n")
                cue_file.write("    INDEX 01 00:02:00\n")
            else:
                if track_number == 1 or track_number == 3:
                    # It's the first track of the single-density or high-density area.
                    cue_file.write("    INDEX 01 00:00:00\n")
                elif track_number == len(gdi_track_lines):
                    # It's the last track on the disc.
                    cue_file.write("    INDEX 00 00:00:00\n")
                    cue_file.write("    INDEX 01 00:03:00\n")
                else:
                    # I think this is correct, but haven't verified it with an actual example (and I'm not even certain if there are allowed to be multiple data tracks in an area on GD-ROM discs).
                    cue_file.write("    INDEX 00 00:00:00\n")
                    cue_file.write("    INDEX 01 00:02:00\n")


def get_sha1hex_for_rvz(rvz_path, show_command_output: bool) -> str:
    with tempfile.TemporaryDirectory() as dolphin_tool_user_folder_name:
        dolphintool_result = subprocess.run(
            ["DolphinTool", "verify", "-u", dolphin_tool_user_folder_name, "-i", str(rvz_path), "--algorithm=sha1"],
            capture_output=True,
            text=True,
        )

    if show_command_output:
        print(dolphintool_result.stderr, end="")

    if dolphintool_result.returncode != 0:
        raise ConversionException("Failed to find SHA-1 using DolphinTool", rvz_path, dolphintool_result.stderr)

    return dolphintool_result.stdout.strip()
