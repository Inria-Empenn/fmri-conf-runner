import glob
import os
from argparse import ArgumentParser

import nibabel as nib

from postprocess.postprocess_service import PostprocessService


def postproc():
    postproc_srv = PostprocessService()

    parser = ArgumentParser(description='Post processing of results')
    parser.add_argument('--results', required=True, type=str, help='path to results')
    args = parser.parse_args()

    basedir = args.results
    mean_path = os.path.join(basedir, 'mean_result.nii')
    ds_path = os.path.join(basedir, 'dataset.csv')

    ids = []
    results = []
    paths = glob.glob(os.path.join(basedir, '*/'), recursive=True)
    for path in paths:
        ids.append(os.path.basename(os.path.dirname(path)))
        results.append(os.path.join(path, '_subject_id_01', 'result.nii'))

    size = len(results)
    if size < 1:
        print(f'No results found in [{basedir}]')
        return
    else:
        print(f'[{size}] results found in [{basedir}]')

    print(f"Generating mean result image from [{size}] results...")
    mean_nifti_image = postproc_srv.get_mean_image(results, 10)
    nib.save(mean_nifti_image, mean_path)
    print(f"Mean result image written to [{mean_path}]")

    print(f"Building dataset from [{size}] results...")
    dataframe = postproc_srv.get_dataframe(basedir, ids)
    dataframe.to_csv(ds_path, index=False, sep=';')
    print(f"Dataset CSV written to [{mean_path}]")


if __name__ == '__main__':
    postproc()
