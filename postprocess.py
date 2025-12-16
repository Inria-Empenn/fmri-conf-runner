import glob
import os
from argparse import ArgumentParser
from datetime import datetime

import nibabel as nib

from postprocess.postprocess_service import PostprocessService


def postproc():
    postproc_srv = PostprocessService()

    parser = ArgumentParser(description='Post processing of results')
    parser.add_argument('--results', required=True, type=str, help='path to results')
    args = parser.parse_args()

    basedir = args.results
    mean_path = os.path.join(basedir, 'mean_result.nii')
    corr_path = os.path.join(basedir, 'correlations.csv')
    ds_path = os.path.join(basedir, 'dataset.csv')

    ids = []
    results = []
    paths = glob.glob(os.path.join(basedir, '*/'), recursive=True)
    for path in paths:
        ids.append(os.path.basename(os.path.dirname(path)))
        results.append(os.path.join(path, 'spmT_0001.nii'))

    size = len(results)
    if size < 1:
        print(f'No results found in [{basedir}]')
        return
    else:
        print(f'[{size}] results found in [{basedir}]')

    # print(f"Generating mean result image from [{size}] results...")
    # mean_nifti_image = postproc_srv.get_mean_image(results, 10)
    # nib.save(mean_nifti_image, mean_path)
    # print(f"Mean result image written to [{mean_path}]")

    print(f"Computing all correlations between [{size}] results...")
    nb_cores = len(os.sched_getaffinity(0))
    print(f"[{nb_cores}] cores available")
    correlations = postproc_srv.get_all_correlations(basedir, ids, nb_cores)
    correlations.to_csv(corr_path, index=False, sep=';')
    print(f"Correlations written to [{corr_path}]")

    print(f"Building dataset from [{size}] results...")
    dataset = postproc_srv.get_dataset(basedir, correlations)
    dataset.to_csv(ds_path, index=False, sep=';')
    print(f"Dataset CSV written to [{ds_path}]")


if __name__ == '__main__':
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S.%f")[:-3]
    print(f"Start [{now}]")
    postproc()
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S.%f")[:-3]
    print(f"End [{now}]")
