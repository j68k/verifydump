import argparse
import logging
import pathlib

from .convert import convert_dump_to_normalized_redump_bincue_folder
from .verify import verify_dumps
from .dat import load_dat


def arg_parser_with_common_args() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=False)
    return arg_parser


def handle_common_args(args):
    logging.basicConfig(format="%(message)s", level=logging.DEBUG if args.verbose else logging.INFO)


def verifydump_main():
    arg_parser = arg_parser_with_common_args()
    arg_parser.add_argument("dat_file")
    arg_parser.add_argument("dump_file_or_folder", nargs="+")
    args = arg_parser.parse_args()

    handle_common_args(args)

    dat = load_dat(pathlib.Path(args.dat_file))
    verify_dumps(dat, [pathlib.Path(i) for i in args.dump_file_or_folder])


def convertdump_main():
    arg_parser = arg_parser_with_common_args()
    arg_parser.add_argument("--output_folder", default=".")
    arg_parser.add_argument("--system", default=None, help="The name of the system the dumps are for. If given, the tool will normalize the .cue file that it outputs to match the Redump conventions for that system if possible. Use the full system name that is in the Redump Datfile's header <name> field, or use the short name for the system that appears in Redump web site URLs.")
    arg_parser.add_argument("dump_file", nargs="+")
    args = arg_parser.parse_args()

    handle_common_args(args)

    for dump_file_name in args.dump_file:
        dump_cue_was_normalized = convert_dump_to_normalized_redump_bincue_folder(pathlib.Path(dump_file_name), pathlib.Path(args.output_folder), system=args.system)
        if not dump_cue_was_normalized and args.system:
            logging.warning(f"The .cue file was not normalized to match Redump conventions because the tool doesn't know how to do that for '{args.system}' dumps")
