import argparse
import logging
import pathlib
import sys

from .convert import ConversionException, convert_chd_to_normalized_redump_dump_folder
from .verify import VerificationException, verify_dumps
from .dat import DatParsingException, load_dat


def arg_parser_with_common_args() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=False)
    arg_parser.add_argument("--show-command-output", action=argparse.BooleanOptionalAction, default=False)
    return arg_parser


def handle_common_args(args):
    logging.basicConfig(format="%(message)s", level=logging.DEBUG if args.verbose else logging.INFO)


def verifydump_main():
    arg_parser = arg_parser_with_common_args()
    arg_parser.add_argument("--allow-cue-file-mismatches", action=argparse.BooleanOptionalAction, default=False)
    arg_parser.add_argument("--extra-cue-source")
    arg_parser.add_argument("dat_file")
    arg_parser.add_argument("dump_file_or_folder", nargs="+")
    args = arg_parser.parse_args()

    handle_common_args(args)

    try:
        dat = load_dat(pathlib.Path(args.dat_file))
    except DatParsingException as e:
        print(f"Error when parsing Datfile: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading Datfile: {e}")
        sys.exit(1)

    (verified_games, errors) = verify_dumps(dat, [pathlib.Path(i) for i in args.dump_file_or_folder], show_command_output=args.show_command_output, allow_cue_mismatches=args.allow_cue_file_mismatches, extra_cue_source=pathlib.Path(args.extra_cue_source) if args.extra_cue_source else None)

    if len(verified_games) > 1:
        print(f"Successfully verified {len(verified_games)} dumps")

    if len(errors) > 0:
        print(f"{len(errors)} dumps had errors:" if len(errors) > 1 else "1 dump had an error:", file=sys.stderr)

        for error in errors:
            if isinstance(error, ConversionException):
                print(f'Failed to process "{error.converted_file_path}" to verify it: {error}', file=sys.stderr)
                if error.tool_output:
                    print(error.tool_output, end="", file=sys.stderr)
            elif isinstance(error, VerificationException):
                print(error, file=sys.stderr)
            else:
                raise error  # wut?

    sys.exit(1 if len(errors) > 0 else 0)


def convertdump_main():
    tool_name = pathlib.Path(sys.argv[0]).stem

    arg_parser = arg_parser_with_common_args()
    arg_parser.add_argument("--output-folder", default=".")
    arg_parser.add_argument("--system", default=None, help=f"The name of the system the dumps are for. If given, {tool_name} will attempt to normalize the .cue file that it outputs to match the Redump conventions for that system if possible. Use the full system name that is in the Redump Datfile's header <name> field, or use the short name for the system that appears in Redump web site URLs.")
    arg_parser.add_argument("dump_file", nargs="+")
    args = arg_parser.parse_args()

    handle_common_args(args)

    for dump_file_name in args.dump_file:
        dump_cue_was_normalized = convert_chd_to_normalized_redump_dump_folder(
            pathlib.Path(dump_file_name),
            pathlib.Path(args.output_folder),
            system=args.system,
            show_command_output=args.show_command_output,
        )

        if not dump_cue_was_normalized and args.system:
            logging.warning(f"The .cue file was not normalized to match Redump conventions because {tool_name} doesn't know how to do that for '{args.system}' dumps")
