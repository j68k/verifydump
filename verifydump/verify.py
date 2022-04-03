import hashlib
import logging
import os
import pathlib
import shutil
import typing
from xml.etree import ElementTree


class Dat:
    def __init__(self, system: str):
        self.system = system
        self.games = []
        self.roms_by_sha1hex = {}


class Game:
    def __init__(self, name: str, dat: Dat):
        self.name = name
        self.roms = []
        self.dat = dat


class ROM:
    def __init__(self, name: str, size: int, sha1hex: str, game: Game):
        self.name = name
        self.size = size
        self.sha1hex = sha1hex
        self.game = game


class DatParsingException(Exception):
    pass


class DatParser:
    def __init__(self):
        self.tag_path = []
        self.dat = None
        self.game = None

    def start(self, tag, attribs):
        self.tag_path.append(tag)

        if self.tag_path == ["datafile", "game"]:
            if self.game:
                raise DatParsingException("Found a <game> within another <game>")
            if not self.dat:
                raise DatParsingException("Found a <game> before the <header> was parsed")

            self.game = Game(name=self._get_required_attrib(attribs, "name"), dat=self.dat)

        elif self.tag_path == ["datafile", "game", "rom"]:
            if not self.game:
                raise DatParsingException("Found a <rom> that was not within a <game>")

            try:
                size_attrib = self._get_required_attrib(attribs, "size")
                size = int(size_attrib)
            except ValueError:
                raise DatParsingException(f"<rom> has size attribute that is not an integer: {size_attrib}")

            rom = ROM(
                name=self._get_required_attrib(attribs, "name"),
                size=size,
                sha1hex=self._get_required_attrib(attribs, "sha1"),
                game=self.game,
            )

            self.game.roms.append(rom)
            self.dat.roms_by_sha1hex[rom.sha1hex] = rom

    def _get_required_attrib(self, attribs, name) -> str:
        value = attribs.get(name)
        if not value:
            raise DatParsingException(f"Found a <{self.tag_path[-1]}> without a {name} attribute")
        return value

    def end(self, tag):
        if self.tag_path == ["datafile", "game"]:
            self.dat.games.append(self.game)
            self.game = None

        self.tag_path.pop()

    def data(self, data):
        if self.tag_path == ["datafile", "header", "name"]:
            self.dat = Dat(system=data)

    def close(self) -> Dat:
        return self.dat


class FileLikeParserFeeder:
    def __init__(self, parser):
        self.parser = parser

    def write(self, b):
        self.parser.feed(b)


def load_dat(dat_path: pathlib.Path) -> Dat:
    logging.debug(f"Loading Dat file: {dat_path}")
    with open(dat_path, "rb") as dat_file:
        xml_parser = ElementTree.XMLParser(target=DatParser())
        shutil.copyfileobj(dat_file, FileLikeParserFeeder(xml_parser))
        dat = xml_parser.close()
        logging.info(f"Dat loaded successfully with {len(dat.games)} games")
        return dat


class VerificationException(Exception):
    pass


def verify_dump(dump_path: pathlib.Path):
    logging.debug(f"Verifying dump file: {dump_path}")
    pass  # FIXME implement


class FileLikeHashUpdater:
    def __init__(self, hash):
        self.hash = hash

    def write(self, b):
        self.hash.update(b)


def verify_bincue_folder_dump(dat: Dat, dump_folder: pathlib.Path):
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
                    verify_dump(full_path)

        else:
            verify_dump(dump_file_or_folder_path)
