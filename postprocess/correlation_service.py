import numpy as np
import pandas as pd
from nibabel import load, Nifti1Image
from nibabel.processing import resample_from_to
from numpy import corrcoef, reshape
from pandas import DataFrame
from scipy.stats import spearmanr
from typing import List


class CorrelationService:
    def compute_correlations(self, image, images: List[str]) -> DataFrame:
        print(f"Computing correlations from [{image}] to [{len(images)}] images... ", end='')
        dfs = []
        for img in images:
            corr = self.get_correlation_coefficient(image, img, 'spearman')
            dfs.append(pd.DataFrame([[image, img, corr]], columns=['source', 'target', 'correlation']))
        merged = pd.concat(dfs, ignore_index=True)
        print("OK")
        return merged.sort_values(by='correlation', ascending=False)

    def get_correlation_coefficient(self,
            file_1: str, file_2: str, method: str = 'pearson') -> float:
        """ Return the correlation coefficient of two images.

            Arguments :
                - file_1, str - path to the first image
                - file_2, str - path to the second image ; file_2 will be resampled on file_1
                - method, str - either 'pearson', or 'spearman': the correlation method to use
                - reslice_on_file_2, bool - set to :
                    - True if you wish to reslice file_1 on file_2
                    - False otherwise

            Returns :
                - _, float - the correlation coefficient of the two input images,
                using the passed method
        """

        # Load images
        image_1 = load(file_1)
        image_2 = load(file_2)

        # Set masking using NaN's
        image_1 = self.mask_using_zeros(image_1)
        image_2 = self.mask_using_zeros(image_2)

        # Resample using nearest neighbours
        image_2 = resample_from_to(image_2, image_1, order=0)

        # Make 1D vectors from the images data
        data_1 = reshape(image_1.get_fdata(), -1)
        data_2 = reshape(image_2.get_fdata(), -1)

        # Compute the correlation coefficient
        if method == 'pearson':
            return corrcoef(data_1, data_2)[0][1]
        if method == 'spearman':
            return spearmanr(data_1, data_2).correlation
        if method == 'dice':
            return self.get_dice(data_1, data_2)
        if method == 'jaccard':
            return self.get_jaccard(data_1, data_2)

        raise AttributeError(f'Wrong correlation method provided: {method}.')

    def get_dice(self, data_1: np.ndarray, data_2: np.ndarray) -> float:
        """
        Return the DICE score between two images data
        :param data_1:
        :param data_2:
        :return:
        """
        # Binarize
        binary1 = data_1 > 0
        binary2 = data_2 > 0

        # Compute intersection + volumes
        intersection = np.logical_and(binary1, binary2).sum()
        volume = binary1.sum() + binary2.sum()

        # Avoid divide by 0
        if volume == 0:
            return 0.0

        return (2. * intersection) / volume

    def get_jaccard(self, data_1: np.ndarray, data_2: np.ndarray) -> float:
        """
        Return the Jaccard Index between two images data
        :param data_1:
        :param data_2:
        :return:
        """
        # Binarize
        binary1 = data_1 > 0
        binary2 = data_2 > 0

        # Compute intersection + union
        intersection = np.logical_and(binary1, binary2).sum()
        union = np.logical_or(binary1, binary2).sum()

        # Avoid division by zero
        if union == 0:
            return 0.0

        return intersection / union

    def mask_using_zeros(self, data_image: Nifti1Image) -> Nifti1Image:
        """ Mask an image by replacing NaNs with zeros.

            Arguments:
                - data_image, nibabel.Nifti1Image : the image to mask

            Returns:
                - the masked image as nibabel.Nifti1Image
        """

        # Get data from the image
        data = data_image.get_fdata()

        # Replace NaNs by zeros
        data[np.isnan(data)] = 0.0

        # Return data as an image
        return Nifti1Image(data, data_image.affine)
