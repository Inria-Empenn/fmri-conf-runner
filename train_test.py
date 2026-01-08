import os
from argparse import ArgumentParser

import numpy as np
import pandas as pd

from postprocess.postprocess_service import PostprocessService


def train_test():
    postproc_srv = PostprocessService()

    parser = ArgumentParser(description='Post processing of results')
    parser.add_argument('--results', required=True, type=str, help='path to results')
    parser.add_argument('--dataset', required=True, type=str, help='name of dataset CSV in results')
    parser.add_argument('--iter', required=True, type=int, help='iteration number')
    args = parser.parse_args()
    basedir = args.results
    ds = args.dataset
    iteration = args.iter
    dataset = pd.read_csv(os.path.join(f'{basedir}', f'{ds}'), delimiter=';')
    dataset = dataset[dataset['id'] != 'ref']
    postproc_srv.get_train_test(basedir, dataset, iteration)

if __name__ == '__main__':
    train_test()

