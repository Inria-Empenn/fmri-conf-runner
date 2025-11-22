import os
import time
from typing import Optional, List

from core.data_descriptor import DataDescriptor
from core.file_service import FileService, CONFIG_CSV
from core.workflow_service import WorkflowService


class RunService:
    file_srv = FileService()
    workflow_srv = WorkflowService()

    def check_inputs(self, data_desc: DataDescriptor):
        for sub in data_desc.subjects:
            for key, value in data_desc.input.items():
                path = os.path.join(data_desc.data_path, value.replace('{subject_id}', sub))
                if not os.path.exists(path):
                    print(f"Input [{path}] does not exists")
                    return False
                else:
                    if os.path.getsize(path) <= 0:
                        print(f"Input [{path}] is empty")
                        return False
                    else:
                        return True

    def run(self, data_desc: DataDescriptor, configs: List[dict], ref: Optional[dict]):

        if not self.check_inputs(data_desc):
            print(f"Running interrupted.")
            return

        self.file_srv.write_data_descriptor(data_desc)


        if ref is not None:
            self.run_ref(data_desc, ref)

        total_configs = len(configs)
        total_subs = len(data_desc.subjects)

        cpt = 1
        print(f"Running [{total_configs}] configurations for [{total_subs}] subjects to [{data_desc.result_path}]...")
        for config in configs:
            hashconf = self.file_srv.hash_config(config)
            conf_dir = os.path.join(data_desc.result_path, hashconf)

            print(f"Running config [{hashconf}][{cpt}/{total_configs}]...")
            start = time.perf_counter()

            subjects = self.file_srv.filter_processed_subjects(data_desc, hashconf)
            if len(subjects) > 0:
                os.makedirs(conf_dir, exist_ok=True)
                self.file_srv.write_config2csv(config, os.path.join(conf_dir, CONFIG_CSV))

                # subject-level
                sub_workflow = self.workflow_srv.build_subject_workflow(config, subjects, data_desc, hashconf)
                self.workflow_srv.run(sub_workflow, conf_dir)

            if total_subs > 1:
                # group-level
                group_workflow = self.workflow_srv.build_group_workflow(config, data_desc, hashconf)
                self.workflow_srv.run(group_workflow, conf_dir)

            cpt += 1
            self.print_elapsed(start, hashconf)

    def run_ref(self, data_desc: DataDescriptor, ref: dict):
        name = 'ref'
        conf_dir = os.path.join(data_desc.result_path, name)
        total_subs = len(data_desc.subjects)

        print(f"Running reference configuration for [{total_subs}] subjects to [{conf_dir}]...")
        start = time.perf_counter()

        subjects = self.file_srv.filter_processed_subjects(data_desc, name)
        if len(subjects) > 0:
            os.makedirs(conf_dir, exist_ok=True)
            self.file_srv.write_config2csv(ref, os.path.join(conf_dir, CONFIG_CSV))

            # subject-level
            workflow = self.workflow_srv.build_subject_workflow(ref, data_desc, name)
            self.workflow_srv.run(workflow, conf_dir)

        if total_subs > 1:
            # group-level
            group_workflow = self.workflow_srv.build_group_workflow(ref, data_desc, name)
            self.workflow_srv.run(group_workflow, conf_dir)

        self.print_elapsed(start, name)
        return conf_dir

    def print_elapsed(self, start, conf):
        elapsed = time.perf_counter() - start
        HH = int(elapsed // 3600)
        MM = int((elapsed % 3600) // 60)
        SS = int(elapsed % 60)
        sss = int((elapsed * 1000) % 1000)
        print(f"[{conf}] finished - Elapsed time [{HH:02d}:{MM:02d}:{SS:02d}.{sss:03d}]")
