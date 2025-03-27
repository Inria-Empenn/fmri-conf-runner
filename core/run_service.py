import os
from typing import Optional, List

from core.data_descriptor import DataDescriptor
from core.file_service import FileService, MEAN_NII, RESULT_NII, CONFIG_CSV
from core.workflow_service import WorkflowService


class RunService:
    file_srv = FileService()
    workflow_srv = WorkflowService()

    def run(self, data_desc: DataDescriptor, configs: List[dict], ref: Optional[dict]):

        self.file_srv.write_data_descriptor(data_desc)

        conf_ids = []

        if ref is not None:
            self.run_ref(data_desc, ref)
            conf_ids.append('ref')

        size = len(configs)
        print(f"Running [{size}] configurations to [{data_desc.result_path}]...")
        for config in configs:
            hashconf = self.file_srv.hash_config(config)
            if self.file_srv.already_executed(data_desc, hashconf):
                print(f"Skipping config [{hashconf}] : [result.nii] found for all [{len(data_desc.subjects)}] subjects")
                continue

            conf_dir = os.path.join(data_desc.result_path, hashconf)
            os.makedirs(conf_dir, exist_ok=True)
            conf_ids.append(hashconf)

            self.file_srv.write_config2csv(config, os.path.join(conf_dir, CONFIG_CSV))

            workflow = self.workflow_srv.build_workflow(config, data_desc, hashconf)
            self.workflow_srv.run(workflow, conf_dir)

            results = []
            for sub in data_desc.subjects:
                results.append(os.path.join(conf_dir, f'_subject_id_{sub}', RESULT_NII))

            if len(results) > 1:
                print(f"Write mean result image for configuration [{hashconf}]...")
                self.file_srv.write_mean_image(results, os.path.join(conf_dir, MEAN_NII))

        print(f"Running finished.")

    def run_ref(self, data_desc: DataDescriptor, ref: dict):
        name = 'ref'

        if self.file_srv.already_executed(data_desc, name):
            print(f"Skipping config [{name}] : [result.nii] found for all [{len(data_desc.subjects)}] subjects")
            return

        result_path = data_desc.result_path
        conf_dir = os.path.join(result_path, name)
        os.makedirs(conf_dir, exist_ok=True)
        print(f"Running reference configuration to [{result_path}]...")

        self.file_srv.write_config2csv(ref, os.path.join(conf_dir, CONFIG_CSV))

        workflow = self.workflow_srv.build_workflow(ref, data_desc, 'ref')
        self.workflow_srv.run(workflow, conf_dir)

        results = []
        for sub in data_desc.subjects:
            results.append(os.path.join(conf_dir, f'_subject_id_{sub}', RESULT_NII))

        if len(results) > 1:
            print(f"Write mean result image for configuration [{name}]...")
            self.file_srv.write_mean_image(results, os.path.join(conf_dir, MEAN_NII))

        print(f"Running reference configuration finished")

        return conf_dir
