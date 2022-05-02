import logging
import os
import pathlib
import re
import subprocess
import tempfile
import zipfile


class ConversionException(Exception):
    def __init__(self, message: str, converted_file_path: pathlib.Path, tool_output: str):
        super().__init__(message)
        self.converted_file_path = converted_file_path
        self.tool_output = tool_output


def convert_chd_to_normalized_redump_dump_folder(chd_path: pathlib.Path, redump_dump_folder: pathlib.Path, system: str, show_command_output: bool, extra_cue_source: pathlib.Path) -> bool:
    """
    Convert a dump file to Redump format in the specified folder, normalizing it to match the Redump conventions for the given system if applicable and possible.

    Returns a tuple `(dump_was_normalized, cue_file_was_replaced)`. `dump_was_normalized` is True if the dump was normalized, or False if we don't know how to normalize dumps for the given system. If we do know how to normalize for the given system but normalization fails for some reason, then an exception will be raised. `cue_file_was_replaced` is True if the .cue file that we attempted to create from the .chd was replaced with one from `extra_cue_source`. `cue_file_was_replaced` is False if the dump was converted to another format (e.g. .iso) that doesn't use a .cue file, if no .cue file for this dump was found in the `extra_cue_source`, or if the .cue file that we generated already matched the one provided in the `extra_cue_source`.
    """

    cue_file_path = pathlib.Path(redump_dump_folder, chd_path.stem + ".cue")
    convert_chd_to_bincue(chd_path, cue_file_path, show_command_output)
    dump_was_normalized = normalize_redump_bincue_dump_for_system(cue_file_path, system)
    cue_file_was_replaced = replace_cue_file_if_replacement_exists_and_does_not_match(cue_file_path, extra_cue_source=extra_cue_source)
    return (dump_was_normalized, cue_file_was_replaced)


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


def normalize_redump_bincue_dump_for_system(cue_file_path: pathlib.Path, system: str) -> bool:
    dump_path = cue_file_path.parent
    dump_name = cue_file_path.stem

    has_multiple_tracks = len(list(dump_path.glob(f"{dump_name} (Track *).bin"))) > 1
    if not has_multiple_tracks:
        original_bin_name = f"{dump_name} (Track 1).bin"
        single_track_bin_name = f"{dump_name}.bin"

        logging.debug(f"Renaming '{original_bin_name}' to '{single_track_bin_name}' because there is only one .bin file in the dump")

        os.rename(
            pathlib.Path(dump_path, original_bin_name),
            pathlib.Path(dump_path, single_track_bin_name),
        )

        cue_file_path.write_text(cue_file_path.read_text().replace(f'FILE "{original_bin_name}"', f'FILE "{single_track_bin_name}"'))

    is_cue_iso_compatible = not has_multiple_tracks and re.match(r'^\s*FILE\s+"' + re.escape(f"{dump_name}.bin") + r'"\s*BINARY\s+TRACK 01 MODE1/2048\s+INDEX 01 00:00:00\s*$', cue_file_path.read_text())
    if is_cue_iso_compatible:
        logging.debug(f"'{cue_file_path.name}' is .iso compatible so converting dump to .iso and discarding .cue")

        single_track_bin_path = pathlib.Path(dump_path, single_track_bin_name)
        iso_file_path = pathlib.Path(dump_path, f"{dump_name}.iso")

        single_track_bin_path.rename(iso_file_path)
        cue_file_path.unlink()

    system_lower = system.lower() if system else system

    if system_lower in ("Sony - PlayStation".lower(), "psx"):
        return True
    elif system_lower in ("Sony - PlayStation 2".lower(), "ps2"):
        return True
    elif system_lower in ("Sega - Saturn".lower(), "ss"):
        # About 70% of the Saturn .cue files have the "CATALOG 0000000000000" line. Unfortunately there doesn't seem to be a pattern for which files have it, but adding it will be correct more often than not.
        cue_file_path.write_text(f"CATALOG 0000000000000\n{cue_file_path.read_text()}")
        return True
    else:
        return False


def replace_cue_file_if_replacement_exists_and_does_not_match(cue_file_path: pathlib.Path, extra_cue_source: pathlib.Path) -> bool:
    if not extra_cue_source:
        return False

    if extra_cue_source.is_dir():
        extra_cue_file_path = pathlib.Path(extra_cue_source, cue_file_path.name)
        return replace_cue_file_if_replacement_exists_and_does_not_match(cue_file_path=cue_file_path, extra_cue_source=extra_cue_file_path)

    extra_cue_file_path = extra_cue_source

    if not extra_cue_file_path.exists():
        logging.debug(f'No replacement for "{cue_file_path.name}" found in extra .cue source')
        return False

    if extra_cue_file_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(extra_cue_file_path) as zip:
            try:
                zip_member_info = zip.getinfo(cue_file_path.name)
            except KeyError:
                logging.debug(f'No replacement for "{cue_file_path.name}" found in extra .cue zip')
                return False

            with zip.open(zip_member_info) as zip_member:
                extra_cue_file_bytes = zip_member.read()
    else:
        extra_cue_file_bytes = extra_cue_file_path.read_bytes()

    if not cue_file_path.exists():
        logging.debug(f'Using replacement for "{cue_file_path.name}" because we didn\'t generate a .cue file')
        cue_file_path.write_bytes(extra_cue_file_bytes)
        return True

    cue_file_bytes = cue_file_path.read_bytes()

    if cue_file_bytes != extra_cue_file_bytes:
        logging.debug(f'Using replacement for "{cue_file_path.name}" because generated file doesn\'t match the provided one')
        cue_file_path.write_bytes(extra_cue_file_bytes)
        return True

    logging.debug(f'Not replacing "{cue_file_path.name}" with provided file because it matches already')
    return False


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
