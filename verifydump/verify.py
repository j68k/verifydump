import logging
import os
import pathlib
import typing


def load_dat(dat_path: pathlib.Path):
    logging.debug(f"Loading DAT file: {dat_path}")
    pass  # FIXME implement


def verify_dump(dump_path: pathlib.Path):
    logging.debug(f"Verifying dump file: {dump_path}")
    pass  # FIXME implement


def verify_dumps(dump_file_or_folder_paths: typing.List[pathlib.Path]):
    for dump_file_or_folder_path in dump_file_or_folder_paths:
        if dump_file_or_folder_path.is_dir():
            for (dir_path, _, filenames) in os.walk(dump_file_or_folder_path, followlinks=True):
                for filename in filenames:
                    if not filename.lower().endswith(".chd"):
                        continue

                    full_path = pathlib.Path(dump_file_or_folder_path, dir_path, filename)
                    verify_dump(full_path)

        else:
            verify_dump(dump_file_or_folder_path)
