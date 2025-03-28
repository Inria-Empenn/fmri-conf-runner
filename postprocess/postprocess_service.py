import os

import nibabel as nib
import numpy as np
import pandas as pd
from typing import List

from postprocess.correlation_service import CorrelationService


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
            df['from_ref'] = corr.loc[(corr['source'] == conf_id) & (corr['target'] == 'ref'), 'correlation'].values[0]
            df['from_mean'] = corr.loc[(corr['source'] == conf_id) & (corr['target'] == 'mean'), 'correlation'].values[
                0]
            dataframes.append(df)

        return pd.concat(dataframes, ignore_index=True)

    def get_all_correlations(self, path, ids: List[str]) -> pd.DataFrame:

        data = []
        n = len(ids)
        for i in range(n):
            src = os.path.join(path, ids[i], '_subject_id_01', 'result.nii')
            # Only compute for j >= i
            for j in range(i, n):
                if i == j:
                    corr = 1.0
                else:
                    tgt = os.path.join(path, ids[j], '_subject_id_01', 'result.nii')
                    corr = self.corr_srv.get_correlation_coefficient(src, tgt, 'spearman')
                data.append((ids[i], ids[j], corr))
                if i != j:
                    data.append((ids[j], ids[i], corr))
            # Add correlation from mean
            mean = os.path.join(path, 'mean_result.nii')
            corr = self.corr_srv.get_correlation_coefficient(src, mean, 'spearman')
            data.append((ids[i], 'mean', corr))
            data.append(('mean', ids[i], corr))
            print(f"Processed correlations for [{i+1} / {n}] result")
        dataframe = pd.DataFrame(data, columns=['source', 'target', 'correlation'])
        return dataframe.sort_values(by='correlation', ascending=False)

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

        print("Calculating the mean image...")
        mean_image = total_sum / count

        print("Creating a new NIfTI image with the mean data...")
        mean_nifti = nib.Nifti1Image(mean_image, affine=nib.load(inputs[0]).affine)
        print("Mean image created.")
        return mean_nifti
