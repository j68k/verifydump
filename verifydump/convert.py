import pathlib
import subprocess
import sys


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
        convert_chd_to_bincue_in_folder(dump_file_path, cue_file_path)
    else:
        raise ConversionException(f"{pathlib.Path(sys.argv[0]).stem} doesn't know how to handle '{dump_suffix_lower}' dumps")

    return normalize_redump_cue_file_for_system(cue_file_path, system)


def convert_chd_to_bincue_in_folder(chd_file_path: pathlib.Path, cue_file_path: pathlib.Path):
    subprocess.run(["chdman", "extractcd", "--input", str(chd_file_path), "--output", str(cue_file_path)], check=True)


def normalize_redump_cue_file_for_system(cue_file_path: pathlib.Path, system: str) -> bool:
    return False  # FIXME implement
