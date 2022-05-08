import enum
import hashlib
import logging
import os
import pathlib
import shutil
import sys
import tempfile
import typing
import zipfile

from .convert import ConversionException, convert_chd_to_normalized_redump_dump_folder, get_sha1hex_for_rvz
from .dat import Dat, Game


class VerificationException(Exception):
    pass


@enum.unique
class CueVerificationResult(enum.Enum):
    NO_CUE_NEEDED = enum.auto()
    GENERATED_CUE_VERIFIED_EXACTLY = enum.auto()
    GENERATED_CUE_MATCHES_ESSENTIALS_FROM_EXTRA_CUE = enum.auto()
    GENERATED_CUE_MISMATCH_WITH_NO_EXTRA_CUE_PROVIDED = enum.auto()
    GENERATED_CUE_DOES_NOT_MATCH_ESSENTIALS_FROM_EXTRA_CUE = enum.auto()


class VerificationResult:
    def __init__(self, game: Game, cue_verification_result: CueVerificationResult):
        self.game = game
        self.cue_verification_result = cue_verification_result


def verify_chd(chd_path: pathlib.Path, dat: Dat, show_command_output: bool, allow_cue_mismatches: bool, extra_cue_source: pathlib.Path) -> Game:
    logging.debug(f'Verifying dump file "{chd_path}"')
    with tempfile.TemporaryDirectory() as redump_dump_folder_name:
        redump_dump_folder = pathlib.Path(redump_dump_folder_name)
        convert_chd_to_normalized_redump_dump_folder(chd_path, redump_dump_folder, system=dat.system, show_command_output=show_command_output)
        verification_result = verify_redump_dump_folder(redump_dump_folder, dat=dat, extra_cue_source=extra_cue_source)

        if verification_result.cue_verification_result in (CueVerificationResult.NO_CUE_NEEDED, CueVerificationResult.GENERATED_CUE_VERIFIED_EXACTLY):
            logging.info(f'Dump verified correct and complete: "{verification_result.game.name}"')
        elif verification_result.cue_verification_result == CueVerificationResult.GENERATED_CUE_MATCHES_ESSENTIALS_FROM_EXTRA_CUE:
            logging.info(f'Dump .bin files verified correct and complete, and .cue essential structure matches: "{verification_result.game.name}"')
        elif verification_result.cue_verification_result == CueVerificationResult.GENERATED_CUE_MISMATCH_WITH_NO_EXTRA_CUE_PROVIDED:
            message = f'"{verification_result.game.name}" .bin files verified and complete, but .cue does not match Datfile'

            if allow_cue_mismatches:
                logging.warn(message)
            else:
                message += "\nYou can either supply the original .cue file yourself using the '--extra-cue-source' option so that we can check that the generated .cue file's essential structure is correct, or ignore .cue file errors with the '--allow-cue-file-mismatches' option"
                raise VerificationException(message)
        elif verification_result.cue_verification_result == CueVerificationResult.GENERATED_CUE_DOES_NOT_MATCH_ESSENTIALS_FROM_EXTRA_CUE:
            message = f'"{verification_result.game.name}" .bin files verified and complete, but .cue does not match Datfile or essential structure from extra .cue source'

            if allow_cue_mismatches:
                logging.warn(message)
            else:
                message += f"\nYou can choose to ignore .cue file errors with the '--allow-cue-file-mismatches' option"
                raise VerificationException(message)
        else:
            raise Exception(f"Unhandled CueVerificationResult value: {verification_result.cue_verification_result}")

        return verification_result.game


class FileLikeHashUpdater:
    def __init__(self, hash):
        self.hash = hash

    def write(self, b):
        self.hash.update(b)


# These are simply all the commands that are used in chdman's .cue file writing code:
CHDMAN_SUPPORTED_CUE_COMMANDS = frozenset(("FILE", "TRACK", "PREGAP", "INDEX", "POSTGAP"))


def strip_insignificant_whitespace_and_chdman_unsupported_commands_from_cue(cue_text: str) -> str:
    stripped_cue_lines = (line.strip() for line in cue_text.splitlines())
    supported_cue_lines = (line for line in stripped_cue_lines if line.split(" ", 1)[0].upper() in CHDMAN_SUPPORTED_CUE_COMMANDS)
    return "\n".join(supported_cue_lines)


def verify_redump_dump_folder(dump_folder: pathlib.Path, dat: Dat, extra_cue_source: pathlib.Path) -> VerificationResult:
    verified_roms = []

    cue_verified = False

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

    if cue_verified:
        return VerificationResult(game=game, cue_verification_result=CueVerificationResult.GENERATED_CUE_VERIFIED_EXACTLY)

    game_cue_rom = next((game_rom for game_rom in game.roms if game_rom.name.lower().endswith(".cue")), None)
    if game_cue_rom is None:
        return VerificationResult(game=game, cue_verification_result=CueVerificationResult.NO_CUE_NEEDED)

    if not extra_cue_source:
        return VerificationResult(game=game, cue_verification_result=CueVerificationResult.GENERATED_CUE_MISMATCH_WITH_NO_EXTRA_CUE_PROVIDED)

    if extra_cue_source.is_dir():
        extra_cue_file_path = pathlib.Path(extra_cue_source, game_cue_rom.name)
        if not extra_cue_file_path.exists():
            # This is subtley different from the file-existence check we do below that raises an exception. Here it's reasonable for the user to provide a folder of extra .cue files that doesn't include a .cue for this particular game:
            logging.debug(f'"{game_cue_rom.name}" doesn\'t match Datfile, and no matching file was found in the extra .cue folder to compare it with')
            return VerificationResult(game=game, cue_verification_result=CueVerificationResult.GENERATED_CUE_MISMATCH_WITH_NO_EXTRA_CUE_PROVIDED)
    else:
        extra_cue_file_path = extra_cue_source

    if not extra_cue_file_path.exists():
        raise VerificationException(f'Extra .cue file source "{extra_cue_file_path}" doesn\'t exist')

    if extra_cue_file_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(extra_cue_file_path) as zip:
            try:
                zip_member_info = zip.getinfo(game_cue_rom.name)
            except KeyError:
                logging.debug(f'"{game_cue_rom.name}" doesn\'t match Datfile, and no matching file was found in the extra .cue zip to compare it with')
                return VerificationResult(game=game, cue_verification_result=CueVerificationResult.GENERATED_CUE_MISMATCH_WITH_NO_EXTRA_CUE_PROVIDED)

            with zip.open(zip_member_info) as zip_member:
                extra_cue_bytes = zip_member.read()
    else:
        extra_cue_bytes = extra_cue_file_path.read_bytes()

    extra_cue_sha1hex = hashlib.sha1(extra_cue_bytes).hexdigest()

    if extra_cue_sha1hex != game_cue_rom.sha1hex:
        raise VerificationException(f'Provided extra .cue file "{game_cue_rom.name}" doesn\'t match Datfile')

    with open(pathlib.Path(dump_folder, game_cue_rom.name), "rb") as dump_cue_file:
        dump_cue_bytes = dump_cue_file.read()

    EXPECTED_CUE_ENCODING = "UTF-8"
    try:
        dump_cue_text = dump_cue_bytes.decode(EXPECTED_CUE_ENCODING)
    except UnicodeError:
        raise VerificationException(f'Failed to decode generated .cue file "{game_cue_rom.name}" as {EXPECTED_CUE_ENCODING}')
    try:
        extra_cue_text = extra_cue_bytes.decode(EXPECTED_CUE_ENCODING)
    except UnicodeError:
        raise VerificationException(f'Failed to decode provided .cue file "{game_cue_rom.name}" as {EXPECTED_CUE_ENCODING}')

    if strip_insignificant_whitespace_and_chdman_unsupported_commands_from_cue(dump_cue_text) == strip_insignificant_whitespace_and_chdman_unsupported_commands_from_cue(extra_cue_text):
        logging.debug(f'Dump file "{game_cue_rom.name}" matches essential parts of provided extra .cue file, and extra .cue file matches the Datfile')
        return VerificationResult(game=game, cue_verification_result=CueVerificationResult.GENERATED_CUE_MATCHES_ESSENTIALS_FROM_EXTRA_CUE)

    logging.debug(f'Dump file "{game_cue_rom.name}" does not match essential parts of provided extra .cue file, but extra .cue file does match the Datfile')
    return VerificationResult(game=game, cue_verification_result=CueVerificationResult.GENERATED_CUE_DOES_NOT_MATCH_ESSENTIALS_FROM_EXTRA_CUE)


def verify_rvz(rvz_path: pathlib.Path, dat: Dat, show_command_output: bool) -> Game:
    logging.debug(f'Verifying dump file "{rvz_path}"')

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
    return rom_with_matching_sha1_and_name.game


def verify_dumps(dat: Dat, dump_file_or_folder_paths: typing.List[pathlib.Path], show_command_output: bool, allow_cue_mismatches: bool, extra_cue_source: pathlib.Path) -> tuple[list, list]:
    verified_games = []
    errors = []

    def verify_dump_if_format_is_supported(dump_path: pathlib.Path, error_if_unsupported: bool):
        suffix_lower = dump_path.suffix.lower()
        try:
            if suffix_lower == ".chd":
                verified_games.append(verify_chd(dump_path, dat=dat, show_command_output=show_command_output, allow_cue_mismatches=allow_cue_mismatches, extra_cue_source=extra_cue_source))
            elif suffix_lower == ".rvz":
                verified_games.append(verify_rvz(dump_path, dat=dat, show_command_output=show_command_output))
            elif error_if_unsupported:
                raise VerificationException(f'{pathlib.Path(sys.argv[0]).stem} doesn\'t know how to handle "{suffix_lower}" dumps')
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

    return (verified_games, errors)
