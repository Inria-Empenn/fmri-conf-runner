import os
import time
from typing import Optional, List

import nipype
from core.data_descriptor import DataDescriptor
from core.file_service import FileService, CONFIG_CSV
from core.workflow_service import WorkflowService

class RunService:
    file_srv = FileService()
    workflow_srv = WorkflowService()

    # set to 'false' for debugging, 'true' for prod
    CLEAN_OUTPUTS = 'true'

    def check_inputs(self, data_desc: DataDescriptor):
        ok = True
        for sub in data_desc.subjects:
            for key, value in data_desc.input.items():
                path = os.path.join(data_desc.data_path, value.replace('{subject_id}', sub))
                if not os.path.isfile(path):
                    print(f"[LOG][RUN] Input [{path}] does not exists")
                    ok = False
                elif os.path.getsize(path) == 0:
                    print(f"[LOG][RUN] Input [{path}] is empty")
                    ok = False
        return ok

    def run(self, data_desc: DataDescriptor, configs: List[dict], ref: Optional[dict], nb_procs: int):

        nipype.config.set('execution', 'remove_unnecessary_outputs', self.CLEAN_OUTPUTS)
        print(f"[LOG][RUN] NyPype ['remove_unnecessary_outputs'] is set to [{self.CLEAN_OUTPUTS}]")

        if not self.check_inputs(data_desc):
            print(f"[LOG][RUN] Running interrupted.")
            return

        self.file_srv.write_data_descriptor(data_desc)

        hash_configs = {}

        if ref is not None:
            hash_configs['ref'] = ref
            # self.run_ref(data_desc, ref, nb_procs)

        for config in configs:
            hashconf = self.file_srv.hash_config(config)
            hash_configs[hashconf] = config

        total_configs = len(hash_configs)
        total_subs = len(data_desc.subjects)

        if total_configs == 0:
            return

        cpt = 1
        print(f"[LOG][RUN] Running [{total_configs}] configurations for [{total_subs}] subjects to [{data_desc.result_path}]...")
        for hashconf, config in hash_configs.items():
            conf_dir = os.path.join(data_desc.result_path, hashconf)

            print(f"[LOG][RUN] Running config [{hashconf}][{cpt}/{total_configs}]...")
            start = time.perf_counter()

            subjects = self.file_srv.filter_processed_subjects(data_desc, hashconf)
            if len(subjects) > 0:
                os.makedirs(conf_dir, exist_ok=True)
                self.file_srv.write_config2csv(config, os.path.join(conf_dir, CONFIG_CSV))

                # subject-level
                sub_workflow = self.workflow_srv.build_subject_workflow(config, subjects, data_desc, hashconf, False)
                self.workflow_srv.run(sub_workflow, conf_dir, nb_procs)

                ko_subjects = self.file_srv.check_mask(subjects, data_desc, hashconf)
                if len(ko_subjects) > 0:
                    print(f"[LOG][WARNING][RUN][{hashconf}] [{len(ko_subjects)}] subjects are under mask coverage target.")

            if total_subs > 1:
                # group-level
                group_workflow = self.workflow_srv.build_group_workflow(config, data_desc, hashconf)
                self.workflow_srv.run(group_workflow, conf_dir, nb_procs)

            cpt += 1
            self.print_elapsed(start, nb_procs, hashconf)

    def print_elapsed(self, start, nb_procs, conf):
        elapsed = time.perf_counter() - start
        HH = int(elapsed // 3600)
        MM = int((elapsed % 3600) // 60)
        SS = int(elapsed % 60)
        sss = int((elapsed * 1000) % 1000)
        print(f"[LOG][RUN] Config [{conf}] finished - Elapsed time [{HH:02d}:{MM:02d}:{SS:02d}.{sss:03d}] - [{nb_procs}] cores")
