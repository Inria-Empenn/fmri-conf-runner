import os
from multiprocessing import Pool

import nibabel as nib
import numpy as np
import pandas as pd
from typing import List

from pandas import DataFrame

from core.file_service import FileService, RESULT_NII, MEAN_NII
from postprocess.correlation_service import CorrelationService
from sklearn.model_selection import train_test_split


class PostprocessService:
    corr_srv = CorrelationService()

    def get_dataset(self, path, corr: pd.DataFrame) -> pd.DataFrame:
        dataframes = []
        for conf_id in corr['source'].unique():
            if conf_id == 'ref' or conf_id == 'mean':
                continue
            config = os.path.join(path, str(conf_id), 'config.csv')
            df = pd.read_csv(config, delimiter=';').astype(bool)
            df['id'] = conf_id
            df['from_ref'] = corr.loc[(corr['source'] == conf_id) & (corr['target'] == 'ref'), 'spearman'].values[0]
            df['from_mean'] = corr.loc[(corr['source'] == conf_id) & (corr['target'] == 'mean'), 'spearman'].values[0]
            dataframes.append(df)

        return pd.concat(dataframes, ignore_index=True)

    def get_pairwise_correlation(self, src, tgt, path):
        if src == tgt:
            return src, tgt, 1.0, 1.0, 1.0, 1.0
        else:
            src_nii = os.path.join(path, src, RESULT_NII) if src != 'mean' else os.path.join(path, MEAN_NII)
            tgt_nii = os.path.join(path, tgt, RESULT_NII) if tgt != 'mean' else os.path.join(path, MEAN_NII)
            spear = self.corr_srv.get_correlation_coefficient(src_nii, tgt_nii, 'spearman')
            pear = self.corr_srv.get_correlation_coefficient(src_nii, tgt_nii, 'pearson')
            dice = self.corr_srv.get_correlation_coefficient(src_nii, tgt_nii, 'dice')
            jacc = self.corr_srv.get_correlation_coefficient(src_nii, tgt_nii, 'jaccard')
            return src, tgt, spear, pear, dice, jacc

    def get_all_correlations(self, path, ids: List[str], nb_cores: int) -> pd.DataFrame:
        ids.append('mean')
        n = len(ids)

        args = []
        for i in range(n):
            for j in range(i, n):
                args.append((ids[i], ids[j], path))

        with Pool(processes=nb_cores) as pool:
            results = pool.starmap(self.get_pairwise_correlation, args)

        data = []
        for result in results:
            data.append(result)
            if result[0] != result[1]:
                data.append((result[1], result[0], result[2], result[3], result[4], result[5]))

        dataframe = pd.DataFrame(data, columns=['source', 'target', 'spearman', 'pearson', 'dice', 'jaccard'])
        return dataframe.sort_values(by='spearman', ascending=False)

    def get_mean_image(self, inputs: list, batch_size: int) -> nib.Nifti1Image:
        total_sum = None
        count = 0

        total = len(inputs)

        print(f"Summing the [{total}] images...")
        for i in range(0, total, batch_size):
            batch_paths = inputs[i:i + batch_size]
            batch_images = [nib.load(path).get_fdata() for path in batch_paths]

            # Stack the batch images into a single numpy array
            batch_array = np.stack(batch_images, axis=0)

            # Calculate the sum of the batch
            batch_sum = np.sum(batch_array, axis=0)

            # Accumulate the sum and count
            if total_sum is None:
                total_sum = batch_sum
            else:
                total_sum += batch_sum

            count += len(batch_paths)
            print(f"Summed [{count} / {total}] images")

        print("Calculating the mean image...")
        mean_image = total_sum / count

        print("Creating a new NIfTI image with the mean data...")
        mean_nifti = nib.Nifti1Image(mean_image, affine=nib.load(inputs[0]).affine)
        print("Mean image created.")
        return mean_nifti

    def get_train_test(self, path: str, dataset: pd.DataFrame, train_size: float, iteration: int):
        print(f"Iteration [{iteration}] - Training size [{train_size}]")
        X = dataset['id']
        y = dataset['id']
        X_id_train, X_id_test, y_id_train, y_id_test = train_test_split(X, y, train_size=train_size)

        self.write_subset(X_id_train, dataset, path, f'train_{iteration}')
        self.write_subset(X_id_test, dataset, path, f'test_{iteration}')

    def write_subset(self, ids: [], dataset: DataFrame, path: str, name: str):
        size = len(ids)
        filtered_ds = dataset[dataset['id'].isin(ids)]
        ds_name = f'sub_dataset_{size}_{name}.csv'
        mean_path = os.path.join(path, f'tmp_mean_result_{name}.nii')
        files = []
        for conf_id in ids:
            files.append(os.path.join(path, conf_id, '_subject_id_01', 'result.nii'))
        mean_img = self.get_mean_image(files, 10)
        nib.save(mean_img, mean_path)
        print(f"Computing correlations to mean image for [{size}] results...")
        for index, row in filtered_ds.iterrows():
            img = os.path.join(path, row['id'], '_subject_id_01', 'result.nii')
            filtered_ds.at[index, 'from_mean'] = self.corr_srv.get_correlation_coefficient(mean_path, img, 'spearman')
        filtered_ds.to_csv(os.path.join(path, ds_name),
                       index=False, sep=';')
        print(f"Written to [{ds_name}].")
