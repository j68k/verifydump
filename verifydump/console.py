import argparse
import logging
import pathlib
import sys

from .convert import convert_dump_to_normalized_redump_bincue_folder
from .verify import verify_dumps
from .dat import load_dat


def arg_parser_with_common_args() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=False)
    arg_parser.add_argument("--show-command-output", action=argparse.BooleanOptionalAction, default=False)
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
    verify_dumps(dat, [pathlib.Path(i) for i in args.dump_file_or_folder], show_command_output=args.show_command_output)


def convertdump_main():
    tool_name = pathlib.Path(sys.argv[0]).stem

    arg_parser = arg_parser_with_common_args()
    arg_parser.add_argument("--output-folder", default=".")
    arg_parser.add_argument("--system", default=None, help=f"The name of the system the dumps are for. If given, {tool_name} will normalize the .cue file that it outputs to match the Redump conventions for that system if possible. Use the full system name that is in the Redump Datfile's header <name> field, or use the short name for the system that appears in Redump web site URLs.")
    arg_parser.add_argument("dump_file", nargs="+")
    args = arg_parser.parse_args()

    handle_common_args(args)

    for dump_file_name in args.dump_file:
        dump_cue_was_normalized = convert_dump_to_normalized_redump_bincue_folder(
            pathlib.Path(dump_file_name),
            pathlib.Path(args.output_folder),
            system=args.system,
            show_command_output=args.show_command_output,
        )

        if not dump_cue_was_normalized and args.system:
            logging.warning(f"The .cue file was not normalized to match Redump conventions because {tool_name} doesn't know how to do that for '{args.system}' dumps")
