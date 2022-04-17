import hashlib
import logging
import os
import pathlib
import shutil
import tempfile
import typing

from .convert import convert_dump_to_normalized_redump_bincue_folder
from .dat import Dat, Game


class VerificationException(Exception):
    pass


def verify_dump(dump_path: pathlib.Path, dat: Dat):
    logging.debug(f"Verifying dump file: {dump_path}")
    with tempfile.TemporaryDirectory() as bincue_folder_name:
        bincue_folder = pathlib.Path(bincue_folder_name)
        cue_was_normalized = convert_dump_to_normalized_redump_bincue_folder(dump_path, bincue_folder, system=dat.system)
        verify_bincue_folder_dump(bincue_folder, dat=dat)


class FileLikeHashUpdater:
    def __init__(self, hash):
        self.hash = hash

    def write(self, b):
        self.hash.update(b)


def verify_bincue_folder_dump(dump_folder: pathlib.Path, dat: Dat) -> Game:
    verified_roms = []

    for dump_file_path in dump_folder.iterdir():
        if not dump_file_path.is_file():
            raise VerificationException(f"Unexpected non-file in BIN/CUE folder: {dump_file_path.name}")

        with open(dump_file_path, "rb") as dump_file:
            hash = hashlib.sha1()
            shutil.copyfileobj(dump_file, FileLikeHashUpdater(hash))
            dump_file_sha1hex = hash.hexdigest()

        rom = dat.roms_by_sha1hex.get(dump_file_sha1hex)

        if not rom:
            raise VerificationException(f'SHA-1 of dump file "{dump_file_path.name}" doesn\'t match any file in the Dat')

        if rom.name != dump_file_path.name:
            raise VerificationException(f'Dump file "{dump_file_path.name}" found in Dat, but it should be named "{rom.name}"')

        if rom.size != dump_file_path.stat().st_size:
            print(f"{rom.size} {dump_file_path.stat().st_size}")
            raise VerificationException(f'Dump file "{dump_file_path.name}" found in Dat, but it has the wrong size')

        logging.debug(f'Dump file "{rom.name}" found in Dat and verified')

        if len(verified_roms) > 0:
            previously_verified_roms_game = verified_roms[0].game
            if rom.game != previously_verified_roms_game:
                raise VerificationException(f'Dump file "{rom.name}" is from game "{rom.game.name}", but at least one other file in this dump is from "{previously_verified_roms_game.name}"')

        verified_roms.append(rom)

    if len(verified_roms) == 0:
        raise VerificationException("No dump files found in BIN/CUE folder")

    game = verified_roms[0].game

    for game_rom in game.roms:
        if game_rom not in verified_roms:
            raise VerificationException(f'Game file "{game_rom.name}" is missing in dump')

    for verified_rom in verified_roms:
        if verified_rom not in game.roms:
            # This shouldn't be possible because of the logic above where we check that all files are from the same game, but it feels like it's worth keeping this as a sanity check.
            raise VerificationException(f'Dump has extra file "{verified_rom.name}" that isn\'t associated with the game "{game.name}" in the Dat')

    return game


def verify_dumps(dat: Dat, dump_file_or_folder_paths: typing.List[pathlib.Path]):
    for dump_file_or_folder_path in dump_file_or_folder_paths:
        if dump_file_or_folder_path.is_dir():
            for (dir_path, _, filenames) in os.walk(dump_file_or_folder_path, followlinks=True):
                for filename in filenames:
                    if not filename.lower().endswith(".chd"):
                        continue

                    full_path = pathlib.Path(dump_file_or_folder_path, dir_path, filename)
                    verify_dump(full_path, dat=dat)

        else:
            verify_dump(dump_file_or_folder_path, dat=dat)
