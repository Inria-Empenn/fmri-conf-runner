import os
import time
from typing import Optional, List

import nipype
from nipype import Workflow

from core.data_descriptor import DataDescriptor
from core.file_service import FileService, CONFIG_CSV, COVER_TGT
from core.workflow_service import WorkflowService

class RunService:
    file_srv = FileService()
    workflow_srv = WorkflowService()

    # set to 'false' for debugging, 'true' for prod
    CLEAN_OUTPUTS = 'true'
    PLUGIN = 'MultiProc'

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

    def get_elapsed(self, start):
        elapsed = time.perf_counter() - start
        HH = int(elapsed // 3600)
        MM = int((elapsed % 3600) // 60)
        SS = int(elapsed % 60)
        sss = int((elapsed * 1000) % 1000)
        return f"{HH:02d}:{MM:02d}:{SS:02d}.{sss:03d}"

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

        for config in configs:
            hashconf = self.file_srv.hash_config(config)
            hash_configs[hashconf] = config

        total_configs = len(hash_configs)
        total_subs = len(data_desc.subjects)

        if total_configs == 0:
            return

        cpt = 0

        sub_workflows = dict()
        group_workflows = dict()

        subjects = dict()

        for hashconf, config in hash_configs.items():
            conf_dir = os.path.join(data_desc.result_path, hashconf)

            subjects[hashconf] = self.file_srv.filter_processed_subjects(data_desc, hashconf)
            subs_cpt = len(subjects[hashconf])
            if subs_cpt > 0:
                cpt += 1
                print(f"[LOG][RUN] Building config [{hashconf}][{cpt}/{total_configs}] for [{subs_cpt}/{total_subs}] subjects to [{conf_dir}]...")
                os.makedirs(conf_dir, exist_ok=True)
                self.file_srv.write_config2csv(config, os.path.join(conf_dir, CONFIG_CSV))

                # subject-level
                sub_workflows[hashconf] = self.workflow_srv.build_subject_workflow(config, subjects[hashconf], data_desc, hashconf, False)

            if subs_cpt > 0 or not self.file_srv.has_group_results(data_desc, hashconf):
                group_workflows[hashconf] = self.workflow_srv.build_group_workflow(config, data_desc, hashconf)

        self.run_all(sub_workflows, nb_procs, 'subject')

        ko_workflows = dict()
        for hashconf in sub_workflows.keys():
            ko_subjects = self.file_srv.check_subjects_mask(subjects[hashconf], data_desc, hashconf)
            if len(ko_subjects) > 0:
                print(
                    f"[LOG][WARNING][RUN][{hashconf}] [{len(ko_subjects)}] subjects are under mask coverage target ([{(COVER_TGT * 100)}%]) and will be reprocessed with prealign step")
                ko_workflows[hashconf] = self.workflow_srv.build_subject_workflow(hash_configs[hashconf], ko_subjects, data_desc,
                                                                                  hashconf, True)
        self.run_all(ko_workflows, nb_procs, 'subject')

        for hashconf in ko_workflows.keys():
            still_ko_subjects = self.file_srv.check_subjects_mask(subjects[hashconf], data_desc, hashconf)
            if len(still_ko_subjects) > 0:
                print(
                    f"[LOG][WARNING][RUN][{hashconf}] [{len(still_ko_subjects)}] subjects are still under mask coverage target ([{(COVER_TGT * 100)}%]) after prealign.")

        self.run_all(group_workflows, nb_procs, 'group')

        for hashconf in group_workflows.keys():
            self.file_srv.check_group_mask(data_desc, hashconf)

    def run_all(self, workflows: dict, nb_procs, level: str):
        if len(workflows) == 0:
            return
        master = self.workflow_srv.build_master_workflow(workflows)
        start = time.perf_counter()
        print(f"[LOG][RUN] Running [{len(workflows)}] {level}-level workflows on [{nb_procs}] cores...")
        master.run(self.PLUGIN, plugin_args={'n_procs': nb_procs, 'raise_insufficient': False, 'maxtasksperchild': 1})
        print(
            f"[LOG][RUN] [{len(workflows)}] {level}-level workflows finished - Elapsed time [{self.get_elapsed(start)}] - [{nb_procs}] cores")
