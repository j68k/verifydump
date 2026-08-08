import json
import logging
import pathlib
import sqlite3

from .dat import Game, Dat

cache_connection = None


def initialize_cache(cache_path: pathlib.Path):
    logging.debug(f'Initializing cache DB at {cache_path.name}')
    global cache_connection
    cache_table_creation = "CREATE TABLE IF NOT EXISTS cache (" \
                           "name TEXT PRIMARY KEY NOT NULL UNIQUE, " \
                           "size INTEGER NOT NULL, " \
                           "time INTEGER NOT NULL, " \
                           "data TEXT NOT NULL)"
    cache_connection = sqlite3.connect(cache_path)
    cache_connection.row_factory = sqlite3.Row
    with cache_connection:
        cursor = cache_connection.cursor()
        cursor.execute(cache_table_creation)


def cache_chd(chd_path: pathlib.Path, game: Game, cue_verification_result: str):
    logging.debug(f'Caching {chd_path.name}')
    name = chd_path.name
    size = chd_path.stat().st_size
    time = chd_path.stat().st_mtime_ns
    roms = []
    for rom in game.roms:
        roms.append({"name": rom.name, "size": rom.size, "sha1": rom.sha1hex})
    data = {"cue_verification_result": cue_verification_result, "name": game.name, "roms": roms}
    data_json = json.dumps(data)

    with cache_connection:
        cursor = cache_connection.cursor()
        cursor.execute("INSERT OR REPLACE INTO cache (name, size, time, data) VALUES (?,?,?,?)", [name, size, time, data_json])


def cache_rvz(rvz_path: pathlib.Path, sha1: str):
    logging.debug(f'Caching {rvz_path.name}')
    name = rvz_path.name
    size = rvz_path.stat().st_size
    time = rvz_path.stat().st_mtime_ns

    with cache_connection:
        cursor = cache_connection.cursor()
        cursor.execute("INSERT OR REPLACE INTO cache (name, size, time, data) VALUES (?,?,?,?)",
                       [name, size, time, sha1])


def get_matching_game_from_dat(cached_data: dict, dat: Dat) -> Game:
    cached_game_name = cached_data["name"]
    cached_roms = cached_data["roms"]
    dat_game = next((game for game in dat.games if game.name == cached_game_name), None)
    if not dat_game:
        return None
    if len(cached_roms) != len(dat_game.roms):
        return None
    for cached_rom in cached_roms:
        cached_rom_name = cached_rom["name"]
        cached_rom_size = cached_rom["size"]
        cached_rom_sha1 = cached_rom["sha1"]
        dat_rom = next((rom for rom in dat_game.roms if rom.name == cached_rom_name), None)
        if not dat_rom:
            return None
        if cached_rom_size != dat_rom.size:
            return None
        if cached_rom_sha1 != dat_rom.sha1hex:
            return None
    return dat_game


def get_cached_chd(chd_path: pathlib.Path, dat: Dat) -> tuple[Game, str]:
    logging.debug(f'Checking cache for {chd_path.name}')
    name = chd_path.name
    size = chd_path.stat().st_size
    time = chd_path.stat().st_mtime_ns
    with cache_connection:
        cursor = cache_connection.cursor()
        cursor.execute("SELECT size, time, data FROM cache WHERE name = ?", [name])
        result = cursor.fetchone()
        if result is None:
            return (None, None)
        cached_size = result["size"]
        cached_time = result["time"]
        cached_data_json = result["data"]
    if size != cached_size:
        return (None, None)
    if time != cached_time:
        return (None, None)
    cached_data = json.loads(cached_data_json)
    matched_game = get_matching_game_from_dat(cached_data, dat)
    if not matched_game:
        return (None, None)
    return (matched_game, cached_data["cue_verification_result"])


def get_cached_rvz(rvz_path: pathlib.Path) -> str:
    logging.debug(f'Checking cache for {rvz_path.name}')
    name = rvz_path.name
    size = rvz_path.stat().st_size
    time = rvz_path.stat().st_mtime_ns
    with cache_connection:
        cursor = cache_connection.cursor()
        cursor.execute("SELECT size, time, data FROM cache WHERE name = ?", [name])
        result = cursor.fetchone()
        if result is None:
            return None
        cached_size = result["size"]
        cached_time = result["time"]
        cached_data = result["data"]
    if size != cached_size:
        return None
    if time != cached_time:
        return None
    return cached_data
