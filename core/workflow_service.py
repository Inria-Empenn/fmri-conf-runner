import os

from nipype import Node, IdentityInterface, SelectFiles, DataSink, Merge
from nipype import Workflow
from nipype.algorithms.misc import Gunzip

from core.constants import SPM
from core.data_descriptor import DataDescriptor
from core.file_service import RESULT_NII, CONTRAST_NII
from spm.group_analysis_service import GroupAnalysisService
from spm.preproc_service import PreprocService
from spm.subject_analysis_service import SubjectAnalysisService


class WorkflowService:
    preproc_srv = PreprocService()
    sub_analysis_srv = SubjectAnalysisService()
    group_analysis_srv = GroupAnalysisService()

    PLUGIN = 'MultiProc'

    def run(self, workflow: Workflow, path: str, nb_procs):
        print(f"Workflow [{workflow.name}] running...")
        workflow.run('MultiProc', plugin_args = {'n_procs': nb_procs})
        print(f"Workflow results written to [{path}].")

    def build_subject_workflow(self, config: dict, subjects: list, data_descriptor: DataDescriptor, name: str) -> Workflow:

        is_group = len(subjects) > 1

        workflow = Workflow(name=f'Subject-workflow-{name}')

        output_path = os.path.join(data_descriptor.result_path, name)

        features = []
        for key, value in config.items():
            if value:
                features.append(key)

        src_infos = self.get_infos(subjects)

        nodes = {}
        if 'preprocessing' in features:
            src_infos.features.append('preprocessing')
            nodes.update(self.preproc_srv.get_nodes(features, data_descriptor))
        if 'first_level' in features:
            src_infos.features.append('first_level')
            nodes.update(self.sub_analysis_srv.get_nodes(features, data_descriptor))

        if is_group:
            nodes.update(self.group_analysis_srv.get_nodes(features, data_descriptor))

        workflow.base_dir = data_descriptor.work_path

        inputs = self.get_subject_input(data_descriptor)

        print("Connecting subject-level preprocessing nodes...")
        workflow.connect(src_infos, 'subject_id', inputs, 'subject_id')

        gunzip_func = None
        if data_descriptor.input['func'].endswith('.nii.gz'):
            gunzip_func = self.get_gunzip('func')
            # inputs -> gunzip_func
            workflow.connect(inputs, 'func',
                             gunzip_func, 'in_file')
        gunzip_anat = None
        if data_descriptor.input['anat'].endswith('.nii.gz'):
            gunzip_anat = self.get_gunzip('anat')
            # inputs -> gunzip_anat
            workflow.connect(inputs, 'anat',
                             gunzip_anat, 'in_file')

        # inputs -> motion_correction_realignment
        if gunzip_func:
            # gunzip_func -> motion_correction_realignment
            workflow.connect(gunzip_func, 'out_file',
                             nodes['motion_correction_realignment'], SPM.Realign.Input.in_files)
        else:
            # inputs -> motion_correction_realignment
            workflow.connect(inputs, 'func',
                             nodes['motion_correction_realignment'], SPM.Realign.Input.in_files)

        # distorsion_correction
        # Ignore for now
        # TODO

        if 'slice_timing_correction' in nodes:
            # motion_correction_realignment -> slice_timing_correction
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                             nodes['slice_timing_correction'], SPM.SliceTiming.Input.in_files)
            workflow.connect(nodes['slice_timing_correction'], SPM.SliceTiming.Output.timecorrected_files,
                             nodes['coregistration'], SPM.Coregister.Input.apply_to_files)
        else:
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                             nodes['coregistration'], SPM.Coregister.Input.apply_to_files)

        if "coregistration/source_target/anat_on_func" in features:
            nodes['coregistration'].features.append("coregistration/source_target/anat_on_func")

            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.mean_image,
                             nodes['coregistration'], SPM.Coregister.Input.target)

            if gunzip_anat:
                # gunzip_anat -> coregistration
                workflow.connect(gunzip_anat, 'out_file',
                                 nodes['coregistration'], SPM.Coregister.Input.source)
            else:
                # inputs -> coregistration
                workflow.connect(inputs, 'anat',
                                 nodes['coregistration'], SPM.Coregister.Input.source)

            # coregistered source is anat
            # coregistration -> segmentation
            workflow.connect(nodes['coregistration'], SPM.Coregister.Output.coregistered_source,
                             nodes['segmentation'], SPM.NewSegment.Input.channel_files)

            if 'slice_timing_correction' in nodes:
                workflow.connect(nodes['slice_timing_correction'], SPM.SliceTiming.Output.timecorrected_files,
                                 nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)
            else:
                workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                                 nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)

        elif "coregistration/source_target/func_on_anat" in features:
            nodes['coregistration'].features.append("coregistration/source_target/func_on_anat")
            # motion_correction_realignment -> coregistration

            if gunzip_anat:
                # gunzip_anat -> coregistration
                workflow.connect(gunzip_anat, 'out_file',
                                 nodes['coregistration'], SPM.Coregister.Input.target)
            else:
                # inputs -> coregistration
                workflow.connect(inputs, 'anat',
                                 nodes['coregistration'], SPM.Coregister.Input.target)

            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.mean_image,
                             nodes['coregistration'], SPM.Coregister.Input.source)

            if gunzip_anat:
                # gunzip_anat -> segmentation
                workflow.connect(gunzip_anat, 'out_file',
                                 nodes['segmentation'], SPM.NewSegment.Input.channel_files)
            else:
                # inputs -> segmentation
                workflow.connect(inputs, 'anat',
                                 nodes['segmentation'], SPM.NewSegment.Input.channel_files)

                # coregistration -> spatial_normalization
                workflow.connect(nodes['coregistration'], SPM.Coregister.Output.coregistered_files,
                                 nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)


        # segmentation -> spatial_normalization
        workflow.connect(nodes['segmentation'], SPM.NewSegment.Output.forward_deformation_field,
                         nodes['spatial_normalization'], SPM.Normalize12.Input.deformation_file)

        # spatial_normalization -> spatial_smoothing
        workflow.connect(nodes['spatial_normalization'], SPM.Normalize12.Output.normalized_files,
                         nodes['spatial_smoothing'], SPM.Smooth.Input.in_files)

        ### SUBJECT LEVEL ANALYSIS ###

        print("Connecting subject-level analysis nodes...")

        # input -> sub_level_spec
        if "events" in data_descriptor.input:
            workflow.connect(inputs, "events",
                             nodes['sub_level_spec'], "bids_event_file")

        # spatial_smoothing -> sub_level_spec
        workflow.connect(nodes['spatial_smoothing'], SPM.Smooth.Output.smoothed_files,
                         nodes['sub_level_spec'], 'functional_runs')

        if "sub_level_spec_realignment_parameters" in nodes:
            # motion_correction_realignment -> sub_level_spec_realignment_parameters
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realignment_parameters,
                             nodes['sub_level_spec_realignment_parameters'], "realignment_parameters")
            # sub_level_spec_realignment_parameters -> sub_level_spec
            workflow.connect(nodes['sub_level_spec_realignment_parameters'], "realignment_parameters",
                             nodes['sub_level_spec'], "realignment_parameters")

        # sub_level_spec -> sub_level_design
        workflow.connect(nodes['sub_level_spec'], 'session_info',
                         nodes['sub_level_design'], 'session_info')

        # sub_level_design -> sub_level_model
        workflow.connect(nodes['sub_level_design'], SPM.Level1Design.Output.spm_mat_file,
                         nodes['sub_level_model'], SPM.EstimateModel.Input.spm_mat_file)

        # sub_level_estimate -> sub_level_contrasts
        workflow.connect(nodes['sub_level_model'], SPM.EstimateModel.Output.spm_mat_file,
                         nodes['sub_level_contrasts'], SPM.EstimateContrast.Input.spm_mat_file)
        workflow.connect(nodes['sub_level_model'], SPM.EstimateModel.Output.beta_images,
                         nodes['sub_level_contrasts'], SPM.EstimateContrast.Input.beta_images)
        workflow.connect(nodes['sub_level_model'], SPM.EstimateModel.Output.residual_image,
                         nodes['sub_level_contrasts'], SPM.EstimateContrast.Input.residual_image)

        output = self.get_subject_output(output_path)
        # sub_level_contrasts -> output
        workflow.connect(nodes['sub_level_contrasts'], SPM.EstimateContrast.Output.spmT_images,
                         output,
                         f'{output_path}.@spmT_images')
        workflow.connect(nodes['sub_level_contrasts'], SPM.EstimateContrast.Output.con_images,
                         output,
                         f'{output_path}.@con_images')

        self.check_implemented_features(workflow, features)

        print("Subject-level workflow ready.")
        return workflow

    def build_group_workflow(self, config: dict, data_descriptor: DataDescriptor, name: str) -> Workflow:

        workflow = Workflow(name=f'Group-workflow-{name}')

        output_path = os.path.join(data_descriptor.result_path, name)

        features = []
        for key, value in config.items():
            if value:
                features.append(key)

        nodes = self.group_analysis_srv.get_nodes(features, data_descriptor)

        workflow.base_dir = data_descriptor.work_path

        inputs = self.get_group_input(name, data_descriptor)

        print("Connecting group-level analysis nodes...")

        # group_input -> group_level_design
        workflow.connect(inputs, 'contrasts',
                         nodes['group_level_design'], SPM.OneSampleTTestDesign.Input.in_files)

        # group_level_design -> group_level_model
        workflow.connect(nodes['group_level_design'], SPM.FactorialDesign.Output.spm_mat_file,
                         nodes['group_level_model'], SPM.EstimateModel.Input.spm_mat_file)

        # group_level_model -> group_level_contrasts
        workflow.connect(nodes['group_level_model'], SPM.EstimateModel.Output.spm_mat_file,
                         nodes['group_level_contrasts'], SPM.EstimateContrast.Input.spm_mat_file)
        workflow.connect(nodes['group_level_model'], SPM.EstimateModel.Output.beta_images,
                         nodes['group_level_contrasts'], SPM.EstimateContrast.Input.beta_images)
        workflow.connect(nodes['group_level_model'], SPM.EstimateModel.Output.residual_image,
                         nodes['group_level_contrasts'], SPM.EstimateContrast.Input.residual_image)

        # group_level_contrasts -> output
        workflow.connect(nodes['group_level_contrasts'], SPM.EstimateContrast.Output.spmT_images,
                         self.get_group_output(output_path), f'{output_path}.@spmT_images')

        print("Group-level workflow ready.")

        return workflow

    def check_implemented_features(self, workflow, features):
        impl_features = []
        for node in workflow._get_all_nodes():
            if hasattr(node, 'features'):
                impl_features.extend(node.features)

        impl_features_set = set(impl_features)
        features_set = set(features)
        missing_in_features = impl_features_set - features_set
        missing_in_impl_features = features_set - impl_features_set

        # Print warnings
        if missing_in_features:
            print(
                f"[Implementation error] [{len(missing_in_features)}] features implemented in workflow not present in configuration : [{missing_in_features}]")
        if missing_in_impl_features:
            print(
                f"[Implementation error] [{len(missing_in_impl_features)}] features in configuration not implemented in workflow : [{missing_in_impl_features}]")

    def get_infos(self, subjects):
        name = "infos"
        print(f"Implementing [{name}]...")
        infos = Node(interface=IdentityInterface(fields=['subject_id']), name=name)
        infos.iterables = [('subject_id', subjects)]
        infos.features = ['pipeline']
        print(f"[{name}] added to workflow")
        return infos

    def get_subject_input(self, data_desc: DataDescriptor):
        name = "subject_input"
        print(f"Implementing [{name}]...")
        templates = {}
        for key, value in data_desc.input.items():
            templates[key] = os.path.join(data_desc.data_path, value)
        sub_input = Node(interface=SelectFiles(templates, base_directory=data_desc.data_path), name=name)
        print(f"[{name}] added to workflow")
        return sub_input


    def get_group_input(self, config: str, data_desc: DataDescriptor):
        name = "group_input"
        print(f"Implementing [{name}]...")
        group_input = Node(
            IdentityInterface(fields=['contrasts']),
            name=name
        )
        contrasts = []
        for subject in data_desc.subjects:
            if subject not in data_desc.no_group_subjects:
                contrasts.append(os.path.join(data_desc.result_path, config, f'_subject_id_{subject}', CONTRAST_NII))
            else:
                print(f"Subject [{subject}] will be excluded from group analysis")
        group_input.inputs.contrasts = contrasts
        print(f"[{name}] added to workflow")
        return group_input

    def get_subject_output(self, path: str):
        name = "subject_output"
        print(f"Implementing [{name}]...")
        datasink = Node(interface=DataSink(base_directory=path), name=name)
        datasink.inputs.regexp_substitutions = [(r'spmT_0001.nii', RESULT_NII)]
        print(f"[{name}] added to workflow")
        return datasink

    def get_group_output(self, path: str):
        name = "group_output"
        print(f"Implementing [{name}]...")
        datasink = Node(interface=DataSink(base_directory=path), name=name)
        print(f"[{name}] added to workflow")
        return datasink

    def get_gunzip(self, type: str):
        name = f'gunzip_{type}'
        print(f"Implementing [{name}]...")
        gz = Node(interface=Gunzip(), name=name)
        print(f"[{name}] added to workflow")
        return gz
