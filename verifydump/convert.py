import pathlib


def convert_dump_to_normalized_redump_bincue_folder(dump_file_path: pathlib.Path, bincue_folder: pathlib.Path, system: str) -> bool:
    """
    Convert a dump file to .bin/.cue format in the specified folder and normalize the .cue file's format to match the Redump conventions for the given system if possible.

    Returns True if the .cue file was normalized, or False if we don't know how to normalize .cue files for the given system. If we do know how to normalize for the given system but normalization fails for some reason, then an exception will be raised.
    """
    return False  # FIXME implement
