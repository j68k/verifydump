import logging
import os
import pathlib
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

            rom = ROM(
                name=self._get_required_attrib(attribs, "name"),
                size=self._get_required_attrib(attribs, "size"),
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


def load_dat(dat_path: pathlib.Path) -> Dat:
    logging.debug(f"Loading Dat file: {dat_path}")
    with open(dat_path, "rb") as dat_file:
        xml_parser = ElementTree.XMLParser(target=DatParser())
        xml_parser.feed(dat_file.read())
        dat = xml_parser.close()
        logging.debug(f"Dat loaded successfully with {len(dat.games)} games")
        return dat


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
