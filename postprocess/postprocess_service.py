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
        dataframe = pd.DataFrame(columns=['source', 'target', 'correlation'])
        niis = {'ref': os.path.join(path, 'ref', '_subject_id_01', 'result.nii'),
                'mean': os.path.join(path, 'mean_result.nii')}
        for conf_id in ids:
            niis[conf_id] = os.path.join(path, conf_id, '_subject_id_01', 'result.nii')

        for id_src in niis:
            for id_tgt in niis:
                # This correlation may have already been calculated the other way
                if ((dataframe['source'] == id_tgt) & (dataframe['target'] == id_src)).any():
                    corr = dataframe.loc[(dataframe['source'] == id_tgt) & (dataframe['target'] == id_src), 'correlation'].values[0]
                else:
                    corr = self.corr_srv.get_correlation_coefficient(niis[id_tgt], niis[id_src], 'spearman')
                dataframe.append({'source': id_src, 'target': id_tgt, 'correlation': corr}, ignore_index=True)

        return dataframe.sort_values(by='correlation', ascending=False)

    def get_mean_image(self, inputs: list, batch_size: int) -> nib.Nifti1Image:
        total_sum = None
        count = 0

        total = len(inputs)

        print(f"Summing up the [{total}] images")
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
            print(f"Summed [{count}] images.")

        print("Calculating the mean image...")
        mean_image = total_sum / count

        print("Creating a new NIfTI image with the mean data...")
        mean_nifti = nib.Nifti1Image(mean_image, affine=nib.load(inputs[0]).affine)
        print("Mean image created.")
        return mean_nifti
