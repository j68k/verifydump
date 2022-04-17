import logging
import os
import pathlib
import subprocess
import sys
import tempfile


class ConversionException(Exception):
    pass


def convert_dump_to_normalized_redump_bincue_folder(dump_file_path: pathlib.Path, bincue_folder: pathlib.Path, system: str) -> bool:
    """
    Convert a dump file to .bin/.cue format in the specified folder and normalize the .cue file's format to match the Redump conventions for the given system if possible.

    Returns True if the .cue file was normalized, or False if we don't know how to normalize .cue files for the given system. If we do know how to normalize for the given system but normalization fails for some reason, then an exception will be raised.
    """

    cue_file_path = pathlib.Path(bincue_folder, dump_file_path.stem + ".cue")

    dump_suffix_lower = dump_file_path.suffix.lower()

    if dump_suffix_lower == ".chd":
        convert_chd_to_bincue(dump_file_path, cue_file_path)
    else:
        raise ConversionException(f"{pathlib.Path(sys.argv[0]).stem} doesn't know how to handle '{dump_suffix_lower}' dumps")

    return normalize_redump_bincue_dump_for_system(cue_file_path, system)


def convert_chd_to_bincue(chd_file_path: pathlib.Path, output_cue_file_path: pathlib.Path):
    # Use another temporary directory for the chdman output files to keep those separate from the binmerge output files:
    with tempfile.TemporaryDirectory() as chdman_output_folder_path_name:
        chdman_cue_file_path = pathlib.Path(chdman_output_folder_path_name, output_cue_file_path.name)
        subprocess.run(["chdman", "extractcd", "--input", str(chd_file_path), "--output", str(chdman_cue_file_path)], check=True)
        subprocess.run(["binmerge", "--split", "-o", str(output_cue_file_path.parent), str(chdman_cue_file_path), chdman_cue_file_path.stem], check=True)


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

    return False  # FIXME implement
