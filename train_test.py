import os
from argparse import ArgumentParser

import numpy as np
import pandas as pd

from postprocess.postprocess_service import PostprocessService


def train_test():
    postproc_srv = PostprocessService()

    parser = ArgumentParser(description='Post processing of results')
    parser.add_argument('--results', required=True, type=str, help='path to results')
    parser.add_argument('--iter', required=True, type=int, help='iteration number')
    args = parser.parse_args()
    basedir = args.results
    iteration = args.iter
    dataset = pd.read_csv(os.path.join(basedir, 'extended_dataset.csv'), delimiter=';').drop(columns=['mean_corr'])
    train_sizes = np.linspace(0.1, 0.7, 7).tolist()
    for train_size in train_sizes:
        postproc_srv.get_train_test(basedir, dataset, train_size, iteration)

if __name__ == '__main__':
    train_test()

