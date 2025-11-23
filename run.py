from argparse import ArgumentParser

from core.run_service import RunService
from core.file_service import FileService


def run():
    file_srv = FileService()
    run_srv = RunService()


    parser = ArgumentParser(description='Sample and run configuration')
    parser.add_argument('--configs', type=str, help='path to configurations CSV')
    parser.add_argument('--ref', type=str,
                        help='path to reference configuration CSV')
    parser.add_argument('--data', type=str, required=True,
                        help='path to data descriptor JSON')

    args = parser.parse_args()
    if not (args.ref or args.configs):
        parser.error("At least one of --ref or --configs must be specified")

    configs = []
    if args.configs is not None:
        configs = file_srv.read_config(args.configs)
    ref = None
    if args.ref is not None:
        ref = file_srv.read_config(args.ref)[0]

    data_desc = file_srv.read_data_descriptor(args.data)
    run_srv.run(data_desc, configs, ref)


if __name__ == '__main__':
    run()
