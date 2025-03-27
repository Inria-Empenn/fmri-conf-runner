import os

import nibabel as nib
import numpy as np
import pandas as pd
from typing import List

from postprocess.correlation_service import CorrelationService


class PostprocessService:
    corr_srv = CorrelationService()

    def get_dataframe(self, path, ids: List[str]) -> pd.DataFrame:
        dataframes = []
        ref_contrast = os.path.join(path, 'ref', '_subject_id_01', 'result.nii')
        mean = os.path.join(path, 'mean_result.nii')
        for conf_id in ids:
            contrast = os.path.join(path, conf_id, '_subject_id_01', 'result.nii')
            config = os.path.join(path, conf_id, 'config.csv')
            df = pd.read_csv(config, delimiter=';').astype(bool)
            df['id'] = conf_id
            df['from_ref'] = self.corr_srv.get_correlation_coefficient(contrast, ref_contrast, 'spearman')
            df['from_mean'] = self.corr_srv.get_correlation_coefficient(contrast, mean, 'spearman')
            dataframes.append(df)

        return pd.concat(dataframes, ignore_index=True)

    def get_mean_image(self, inputs: list, batch_size: int) -> nib.Nifti1Image:
        total_sum = None
        count = 0

        for i in range(0, len(inputs), batch_size):
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

        # Calculate the mean image
        mean_image = total_sum / count

        # Create a new NIfTI image with the mean data
        mean_nifti = nib.Nifti1Image(mean_image, affine=nib.load(inputs[0]).affine)

        return mean_nifti