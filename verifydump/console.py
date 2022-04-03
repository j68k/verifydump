import argparse
import logging
import pathlib

from .verify import load_dat, verify_dumps


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=False)
    arg_parser.add_argument("dat_file")
    arg_parser.add_argument("dump_file_or_folder", nargs="+")
    args = arg_parser.parse_args()

    logging.basicConfig(format="%(message)s", level=logging.DEBUG if args.verbose else logging.INFO)

    dat = load_dat(pathlib.Path(args.dat_file))
    verify_dumps(dat, [pathlib.Path(i) for i in args.dump_file_or_folder])
