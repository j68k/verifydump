import argparse
import logging
import pathlib
import shutil
import sys
import tempfile
import zipfile

from .convert import ConversionException, convert_chd_to_normalized_redump_dump_folder, convert_gdi_to_cue
from .verify import VerificationException, verify_dumps
from .dat import DatParsingException, load_dat


def arg_parser_with_common_args() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=False, help="Show more detailed output about what the program is doing")
    arg_parser.add_argument("--show-command-output", action=argparse.BooleanOptionalAction, default=False, help="Show the full output from external commands that are run")
    arg_parser.add_argument("--extra-cue-source", metavar="FILE_OR_FOLDER_OR_ZIP", help=f"A source of .cue files that will be used to verify dumps in cases where {pathlib.Path(sys.argv[0]).stem} can't generate the exact original .cue file itself. These are needed when the original .cue file contains metadata that isn't storable in the .chd format, for example. The value you provide here can be a single .cue file if you're just verifying one dump, or it can be a folder or .zip containing many .cue files (such as the one of the Cuesheets .zip files available on the Redump download page).")
    return arg_parser


def handle_common_args(args):
    logging.basicConfig(format="%(message)s", level=logging.DEBUG if args.verbose else logging.INFO)


def verifydump_main():
    try:
        arg_parser = arg_parser_with_common_args()
        arg_parser.add_argument("--allow-cue-file-mismatches", action=argparse.BooleanOptionalAction, default=False, help=f"If the .cue file that {pathlib.Path(sys.argv[0]).stem} generates doesn't match the original dump or extra provided .cue file then it is usually reported as an error. If this option is used then the mismatch is still reported, but isn't treated as an error.")
        arg_parser.add_argument("dat_file", metavar="dat_file_or_zip", help="The Datfile that your dumps will be verified against. It can be zipped.")
        arg_parser.add_argument("dump_file_or_folder", nargs="+", help="The dump files to verify. Specify any number of .chd files, .rvz files, or folders containing those.")
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

    except KeyboardInterrupt:
        # This handler just stops Python from outputting a potentially-confusing exception message when interrupted with Ctrl-C.
        sys.exit(1)


def convertdump_main():
    arg_parser = arg_parser_with_common_args()
    arg_parser.add_argument("--output-folder", default=".")
    arg_parser.add_argument("--system", default=None, help="The name of the system the dumps are for. Some systems require special handling to correctly convert dumps (such as Dreamcast and other systems that use GD-ROM media). Use the full system name that is in the Redump Datfile's header <name> field, or use the short name for the system that appears in Redump web site URLs.")
    arg_parser.add_argument("dump_file", nargs="+")
    args = arg_parser.parse_args()

    handle_common_args(args)

    for dump_file_name in args.dump_file:
        convert_chd_to_normalized_redump_dump_folder(
            pathlib.Path(dump_file_name),
            pathlib.Path(args.output_folder),
            system=args.system,
            show_command_output=args.show_command_output,
            extra_cue_source=pathlib.Path(args.extra_cue_source) if args.extra_cue_source else None,
        )


def convertgditocue_main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("gdi_file")
    arg_parser.add_argument("cue_file")
    args = arg_parser.parse_args()

    logging.basicConfig(format="%(message)s", level=logging.DEBUG)
    cue_file_path = pathlib.Path(args.cue_file)
    convert_gdi_to_cue(gdi_file_path=pathlib.Path(args.gdi_file), cue_file_path=cue_file_path)


def testgditocueconversion_main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("gdi_zip")
    arg_parser.add_argument("cue_zip")
    args = arg_parser.parse_args()

    logging.basicConfig(format="%(message)s", level=logging.DEBUG)

    with zipfile.ZipFile(args.gdi_zip) as gdi_zip, zipfile.ZipFile(args.cue_zip) as cue_zip, tempfile.TemporaryDirectory() as temp_folder_name:
        temp_folder_path = pathlib.Path(temp_folder_name)

        for gdi_zip_member_info in gdi_zip.infolist():
            temp_gdi_path = pathlib.Path(temp_folder_path, gdi_zip_member_info.filename)
            with open(temp_gdi_path, "wb") as temp_gdi_file, gdi_zip.open(gdi_zip_member_info) as gdi_zip_member_file:
                shutil.copyfileobj(gdi_zip_member_file, temp_gdi_file)

            cue_filename = gdi_zip_member_info.filename.replace(".gdi", ".cue")
            converted_cue_path = pathlib.Path(temp_folder_path, cue_filename)

            convert_gdi_to_cue(gdi_file_path=temp_gdi_path, cue_file_path=converted_cue_path)

            with cue_zip.open(cue_filename) as cue_zip_member_file:
                if cue_zip_member_file.read() == converted_cue_path.read_bytes():
                    logging.info(f"Converted file matches: {cue_filename}")
                else:
                    logging.error(f"Converted file does not match: {cue_filename}")
