import hashlib
import logging
import os
import pathlib
import shutil
import sys
import tempfile
import typing

from .convert import ConversionException, convert_chd_to_normalized_redump_dump_folder, get_sha1hex_for_rvz
from .dat import Dat, Game


class VerificationException(Exception):
    pass


class VerificationResult:
    def __init__(self, game: Game, cue_verified: bool):
        self.game = game
        self.cue_verified = cue_verified


def verify_chd(chd_path: pathlib.Path, dat: Dat, show_command_output: bool) -> Game:
    logging.debug(f"Verifying dump file: {chd_path}")
    with tempfile.TemporaryDirectory() as redump_dump_folder_name:
        redump_dump_folder = pathlib.Path(redump_dump_folder_name)
        cue_was_normalized = convert_chd_to_normalized_redump_dump_folder(chd_path, redump_dump_folder, system=dat.system, show_command_output=show_command_output)
        verification_result = verify_redump_dump_folder(redump_dump_folder, dat=dat)

        if verification_result.cue_verified:
            logging.info(f'Dump verified correct and complete: "{verification_result.game.name}"')
        else:
            if cue_was_normalized:
                logging.warn(f'Dump .bin files verified and complete, but .cue does not match Datfile: "{verification_result.game.name}"')
            else:
                logging.warn(f'Dump .bin files verified and complete, and .cue does not match Datfile, but {pathlib.Path(sys.argv[0]).stem} doesn\'t know how to process .cue files for this platform so that is expected: "{verification_result.game.name}"')

        return verification_result.game


class FileLikeHashUpdater:
    def __init__(self, hash):
        self.hash = hash

    def write(self, b):
        self.hash.update(b)


def verify_redump_dump_folder(dump_folder: pathlib.Path, dat: Dat) -> VerificationResult:
    verified_roms = []

    cue_verified = True  # Not every dump will have a .cue so assume it's verified unless we do actually find one and it fails.

    for dump_file_path in dump_folder.iterdir():
        if not dump_file_path.is_file():
            raise VerificationException(f"Unexpected non-file in dump folder: {dump_file_path.name}")

        dump_file_is_cue = dump_file_path.suffix.lower() == ".cue"

        with open(dump_file_path, "rb") as dump_file:
            hash = hashlib.sha1()
            shutil.copyfileobj(dump_file, FileLikeHashUpdater(hash))
            dump_file_sha1hex = hash.hexdigest()

        roms_with_matching_sha1 = dat.roms_by_sha1hex.get(dump_file_sha1hex)

        if not roms_with_matching_sha1:
            if dump_file_is_cue:
                cue_verified = False
                continue
            raise VerificationException(f'SHA-1 of dump file "{dump_file_path.name}" doesn\'t match any file in the Dat')

        rom_with_matching_sha1_and_name = next((rom for rom in roms_with_matching_sha1 if rom.name == dump_file_path.name), None)

        if not rom_with_matching_sha1_and_name:
            list_of_rom_names_that_match_sha1 = " or ".join([f'"{rom.name}"' for rom in roms_with_matching_sha1])
            raise VerificationException(f'Dump file "{dump_file_path.name}" found in Dat, but it should be named {list_of_rom_names_that_match_sha1}')

        if rom_with_matching_sha1_and_name.size != dump_file_path.stat().st_size:
            print(f"{rom_with_matching_sha1_and_name.size} {dump_file_path.stat().st_size}")
            raise VerificationException(f'Dump file "{dump_file_path.name}" found in Dat, but it has the wrong size')

        rom = rom_with_matching_sha1_and_name

        if dump_file_is_cue:
            cue_verified = True

        logging.debug(f'Dump file "{rom.name}" found in Dat and verified')

        if len(verified_roms) > 0:
            previously_verified_roms_game = verified_roms[0].game
            if rom.game != previously_verified_roms_game:
                raise VerificationException(f'Dump file "{rom.name}" is from game "{rom.game.name}", but at least one other file in this dump is from "{previously_verified_roms_game.name}"')

        verified_roms.append(rom)

    if len(verified_roms) == 0:
        raise VerificationException("No game files found in dump folder")

    game = verified_roms[0].game

    for game_rom in game.roms:
        if game_rom not in verified_roms:
            if not game_rom.name.lower().endswith(".cue"):
                raise VerificationException(f'Game file "{game_rom.name}" is missing in dump')

    for verified_rom in verified_roms:
        if verified_rom not in game.roms:
            # This shouldn't be possible because of the logic above where we check that all files are from the same game, but it feels like it's worth keeping this as a sanity check.
            raise VerificationException(f'Dump has extra file "{verified_rom.name}" that isn\'t associated with the game "{game.name}" in the Dat')

    return VerificationResult(game=game, cue_verified=cue_verified)


def verify_rvz(rvz_path: pathlib.Path, dat: Dat, show_command_output: bool) -> Game:
    logging.debug(f"Verifying dump file: {rvz_path}")

    sha1hex = get_sha1hex_for_rvz(rvz_path, show_command_output=show_command_output)

    roms_with_matching_sha1 = dat.roms_by_sha1hex.get(sha1hex)

    if not roms_with_matching_sha1:
        raise VerificationException(f'SHA-1 of uncompressed version of "{rvz_path}" doesn\'t match any file in the Dat')

    expected_rom_name = rvz_path.with_suffix(".iso").name

    rom_with_matching_sha1_and_name = next((rom for rom in roms_with_matching_sha1 if rom.name == expected_rom_name), None)

    if not rom_with_matching_sha1_and_name:
        list_of_rom_names_that_match_sha1 = " or ".join([f'"{rom.name.replace(".iso", ".rvz")}"' for rom in roms_with_matching_sha1])
        raise VerificationException(f'Dump file "{rvz_path.name}" found in Dat, but it should be named {list_of_rom_names_that_match_sha1}')

    logging.info(f'Dump verified correct and complete: "{rom_with_matching_sha1_and_name.game.name}"')


def verify_dumps(dat: Dat, dump_file_or_folder_paths: typing.List[pathlib.Path], show_command_output: bool) -> list:
    errors = []

    def verify_dump_if_format_is_supported(dump_path: pathlib.Path, error_if_unsupported: bool):
        suffix_lower = dump_path.suffix.lower()
        try:
            if suffix_lower == ".chd":
                verify_chd(dump_path, dat=dat, show_command_output=show_command_output)
            elif suffix_lower == ".rvz":
                verify_rvz(dump_path, dat=dat, show_command_output=show_command_output)
            elif error_if_unsupported:
                raise VerificationException(f"{pathlib.Path(sys.argv[0]).stem} doesn't know how to handle '{suffix_lower}' dumps")
        except VerificationException as e:
            errors.append(e)
        except ConversionException as e:
            errors.append(e)

    for dump_file_or_folder_path in dump_file_or_folder_paths:
        if dump_file_or_folder_path.is_dir():
            for (dir_path, _, filenames) in os.walk(dump_file_or_folder_path, followlinks=True):
                for filename in filenames:
                    full_path = pathlib.Path(dump_file_or_folder_path, dir_path, filename)
                    verify_dump_if_format_is_supported(full_path, error_if_unsupported=False)

        else:
            verify_dump_if_format_is_supported(dump_file_or_folder_path, error_if_unsupported=True)

    return errors
