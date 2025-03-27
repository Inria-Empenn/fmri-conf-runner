import os

from nipype import Node, IdentityInterface, SelectFiles, DataSink
from nipype import Workflow

from core.constants import SPM
from spm.subject_analysis_service import SubjectAnalysisService

from core.data_descriptor import DataDescriptor
from core.file_service import RESULT_NII
from spm.preproc_service import PreprocService


class WorkflowService:
    preproc_srv = PreprocService()
    analysis_srv = SubjectAnalysisService()

    def run(self, workflow: Workflow, path: str, ):
        print(f"Workflow [{workflow.name}] running...")
        workflow.run()
        print(f"Workflow results written to [{path}].")

    def build_workflow(self, config: dict, data_descriptor: DataDescriptor, name: str) -> Workflow:

        workflow = Workflow(name=f'Workflow-{name}')

        output_path = os.path.join(data_descriptor.result_path, name)

        features = []
        for key, value in config.items():
            if value:
                features.append(key)

        nodes = {}
        print("Implementing preprocessing nodes...")
        nodes.update(self.preproc_srv.get_nodes(features, data_descriptor))
        print("Implementing analysis nodes...")
        nodes.update(self.analysis_srv.get_nodes(features, data_descriptor))

        workflow.base_dir = data_descriptor.work_path

        src_infos = self.get_infos(data_descriptor)
        inputs = self.get_input(data_descriptor)

        print("Connecting all nodes...")
        print("Connecting preprocessing nodes...")
        workflow.connect(src_infos, 'subject_id', inputs, 'subject_id')

        # inputs -> motion_correction_realignment
        workflow.connect(inputs, 'func',
                         nodes['motion_correction_realignment'], SPM.Realign.Input.in_files)

        # distorsion_correction
        # Ignore for now

        if 'slice_timing_correction' in nodes:
            # motion_correction_realignment -> slice_timing_correction
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                             nodes['slice_timing_correction'], SPM.SliceTiming.Input.in_files)
            # slice_timing_correction -> spatial_normalization
            workflow.connect(nodes['slice_timing_correction'], SPM.SliceTiming.Output.timecorrected_files,
                             nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)
        else:
            # motion_correction_realignment -> spatial_normalization
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                             nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)

        func_input = SPM.Coregister.Input.target
        anat_input = SPM.Coregister.Input.source

        # motion_correction_realignment -> coregistration
        workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.mean_image,
                         nodes['coregistration'], func_input)
        # inputs -> coregistration
        workflow.connect(inputs, 'anat',
                         nodes['coregistration'], anat_input)

        # coregister -> segmentation
        workflow.connect(nodes['coregistration'], SPM.Coregister.Output.coregistered_source,
                         nodes['segmentation'], SPM.NewSegment.Input.channel_files)

        # segmentation -> spatial_normalization
        workflow.connect(nodes['segmentation'], SPM.NewSegment.Output.forward_deformation_field,
                         nodes['spatial_normalization'], SPM.Normalize12.Input.deformation_file)

        # spatial_normalization -> spatial_smoothing
        workflow.connect(nodes['spatial_normalization'], SPM.Normalize12.Output.normalized_files,
                         nodes['spatial_smoothing'], SPM.Smooth.Input.in_files)

        ### SUBJECT LEVEL ANALYSIS ###

        # input -> sub_level_spec
        if "events" in data_descriptor.input:
            workflow.connect(inputs, "events",
                             nodes['sub_level_spec'], "bids_event_file")

        # spatial_smoothing -> sub_level_spec
        workflow.connect(nodes['spatial_smoothing'], SPM.Smooth.Output.smoothed_files,
                         nodes['sub_level_spec'], 'functional_runs')

        # motion_correction_realignment -> sub_level_spec
        workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realignment_parameters,
                         nodes['sub_level_spec'], "realignment_parameters")

        # sub_level_spec -> sub_level_design
        workflow.connect(nodes['sub_level_spec'], 'session_info',
                         nodes['sub_level_design'], 'session_info')

        # sub_level_design -> sub_level_estimate
        workflow.connect(nodes['sub_level_design'], SPM.Level1Design.Output.spm_mat_file,
                         nodes['sub_level_estimate'], SPM.EstimateModel.Input.spm_mat_file)

        # sub_level_estimate -> sub_level_contrasts
        workflow.connect(nodes['sub_level_estimate'], SPM.EstimateModel.Output.spm_mat_file,
                         nodes['sub_level_contrasts'],  SPM.EstimateContrast.Input.spm_mat_file)
        workflow.connect(nodes['sub_level_estimate'], SPM.EstimateModel.Output.beta_images,
                         nodes['sub_level_contrasts'], SPM.EstimateContrast.Input.beta_images)
        workflow.connect(nodes['sub_level_estimate'], SPM.EstimateModel.Output.residual_image,
                         nodes['sub_level_contrasts'], SPM.EstimateContrast.Input.residual_image)

        # sub_level_contrasts -> output
        output = self.get_output(output_path)
        workflow.connect(nodes['sub_level_contrasts'], SPM.EstimateContrast.Output.spmT_images,
                         output,
                         f'{output_path}.@spmT_images')
        print("Connecting analysis nodes...")

        print("Workflow ready.")
        return workflow

    def get_infos(self, data_desc: DataDescriptor):
        infos = Node(IdentityInterface(fields=['subject_id']), name="infos")
        infos.iterables = [('subject_id', data_desc.subjects)]
        return infos

    def get_input(self, data_desc: DataDescriptor):
        templates = {}
        for key, value in data_desc.input.items():
            templates[key] = os.path.join(data_desc.data_path, value)
        return Node(SelectFiles(templates, base_directory=data_desc.data_path), name="input")

    def get_output(self, path: str):
        datasink = Node(DataSink(base_directory=path), name="output")
        datasink.inputs.regexp_substitutions = [(r'spmT_0001.nii', RESULT_NII)]
        return datasink
