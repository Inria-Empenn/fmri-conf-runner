import csv
import glob
import hashlib
import json
import os
from typing import Union, List

import nibabel as nib
import numpy as np
import pandas as pd

from core.data_descriptor import DataDescriptor

DATA_DESC = "data_desc.json"
HCP_DS = "HCP_dataset.json"

CONFIG_CSV = "config.csv"
CONFIGS_CSV = "configurations.csv"
CORR_MEAN = 'correlations_from_mean.csv'
CORR_REF = 'correlations_from_ref.csv'
CORR = 'correlations.csv'
HCP_EXCLUDED = 'excluded_subjects.csv'

RESULT_NII = 'spmT_0001.nii'
MEAN_NII = 'mean_result.nii'
CONTRAST_NII = 'con_0001.nii'


run_pattern = '[0-3][0-9][0-1][1-9]202[0-9]_[0-2][1-9][0-5][0-9][0-5][0-9]'

class FileService:

    def read_json(self, path: str) -> {}:
        try:
            with open(path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print("File not found.")
        except json.JSONDecodeError:
            print("Error decoding JSON.")
        except Exception as e:
            print(f"Unknown error: {e}")

    def read_data_descriptor(self, path: str) -> DataDescriptor:
        data = self.read_json(path)
        return DataDescriptor(data)

    def write_data_descriptor(self, data_desc: DataDescriptor):
        with open(os.path.join(data_desc.result_path, DATA_DESC), 'w') as file:
            json.dump(data_desc.__dict__, file, indent=4)

    def list_all_runs(self, path: str):
        return glob.glob(os.path.join(path, run_pattern))

    def list_all_nifti(self, path: str):
        return glob.glob(os.path.join(path, run_pattern, '**', '*.nii'), recursive=True)

    def write_config2csv(self, config: Union[dict, List[dict]], path: str):
        configs = []
        if isinstance(config, dict):
            configs.append(config)
        elif isinstance(config, list):
            configs = config

        file = os.path.join(path)
        with open(file, mode='w', newline='') as csv_file:
            writer = csv.writer(csv_file, delimiter=';')
            writer.writerow(configs[0].keys())
            for config in configs:
                writer.writerow(config.values())
        print(f"Configuration(s) saved to [{file}]")
        return file

    def read_config(self, path: str) -> List[dict]:
        configs = []
        df = pd.read_csv(path, delimiter=';')
        for index, row in df.iterrows():
            elements = dict()
            for column, value in row.items():
                elements[column] = value
            configs.append(elements)
        return configs

    def write_dataframe2csv(self, df: pd.DataFrame, path):
        df.to_csv(path, index=False, sep=';')

    def merge_configs2csv(self, ids: List[str], path):
        dataframes = []
        file = os.path.join(path, CONFIGS_CSV)

        for id in ids:
            config = os.path.join(path, id, CONFIG_CSV)
            df = pd.read_csv(config, delimiter=';')
            df['id'] = id
            dataframes.append(df)

        merged = pd.concat(dataframes, ignore_index=True)
        self.write_dataframe2csv(merged, file)

        print(f"[{len(ids)}] configurations merged and saved to [{file}]")
        return file

    def write_mean_image(self, images: List[str], path):
        matrices = []
        header = None
        affine = None
        print(f"Computing mean nifti image from [{len(images)}] images...")
        for img in images:
            loaded = nib.load(img)
            matrices.append(loaded.get_fdata())
            if not header:
                header = loaded.header.copy()
                affine = loaded.affine
        mean = nib.Nifti1Image(np.average(matrices, axis=0), affine, header)
        nib.save(mean, path)
        print(f"Mean nifti image written to [{path}]")
        return os.path.join(path)

    def hash_config(self, config: dict):
        data = json.dumps(config, sort_keys=True).encode('utf-8')
        hashfunc = hashlib.sha256()
        hashfunc.update(data)
        return hashfunc.hexdigest()

    def already_executed(self, data_desc: DataDescriptor, hashconf) -> bool:
        for sub in data_desc.subjects:
            result = os.path.join(data_desc.result_path, hashconf, f"_subject_id_{sub}", "result.nii")
            if not os.path.exists(result):
                return False
        return True

    def filter_processed_subjects(self, data_desc: DataDescriptor, hashconf) -> list:
        subjects = []
        for sub in data_desc.subjects:
            result = os.path.join(data_desc.result_path, hashconf, f"_subject_id_{sub}", RESULT_NII)
            contrast = os.path.join(data_desc.result_path, hashconf, f"_subject_id_{sub}", CONTRAST_NII)
            if not os.path.exists(result) or not os.path.exists(contrast):
                subjects.append(sub)
            else:
                print(f"Results found for subject [{sub}] and config [{hashconf}], skipping.")
        return subjects


