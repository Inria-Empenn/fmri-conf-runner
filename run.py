import os
from argparse import ArgumentParser
from datetime import datetime

from core.run_service import RunService
from core.file_service import FileService


def run():

    file_srv = FileService()
    run_srv = RunService()


    parser = ArgumentParser(description='Sample and run configuration')
    parser.add_argument('--configs', type=str, help='path to configurations CSV')
    parser.add_argument('--index', type=int, help='configs starting index')
    parser.add_argument('--step', type=int, help='number of configs to run')
    parser.add_argument('--ref', type=str,
                        help='path to reference configuration CSV')
    parser.add_argument('--data', type=str, required=True,
                        help='path to data descriptor JSON')

    args = parser.parse_args()
    if not (args.ref or args.configs):
        parser.error("At least one of --ref or --configs must be specified")
    if (args.configs and not (args.index or args.step)):
        parser.error("If --configs is specified, then --index and --step must be specified")

    configs = []
    if args.configs is not None:
        configs = file_srv.read_config(args.configs, args.index, args.step)
    ref = None
    if args.ref is not None:
        ref = file_srv.read_config(args.ref, 0, 1)[0]

    data_desc = file_srv.read_data_descriptor(args.data)
    nb_procs = len(os.sched_getaffinity(0))
    print(f"[{nb_procs}] cores available")
    run_srv.run(data_desc, configs, ref, nb_procs)


if __name__ == '__main__':
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S.%f")[:-3]
    print(f"Start [{now}]")
    run()
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S.%f")[:-3]
    print(f"End [{now}]")
