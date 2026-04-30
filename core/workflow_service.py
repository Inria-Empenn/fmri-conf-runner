import gzip
import os
import shutil

import nibabel as nib
from nipype import Node, IdentityInterface, SelectFiles, DataSink, Merge, Function
from nipype import Workflow
from nipype.algorithms.misc import Gunzip
from nipype.interfaces.minc import Calc
from nipype.interfaces.spm import Coregister
from nipype.interfaces.spm.base import Info as SPMInfo
from traits.trait_base import Undefined, _Undefined

import spm
from core.constants import SPM
from core.data_descriptor import DataDescriptor
from core.file_service import RESULT_NII, CONTRAST_NII, FileService
from spm.group_analysis_service import GroupAnalysisService
from spm.preproc_service import PreprocService
from spm.subject_analysis_service import SubjectAnalysisService


class WorkflowService:
    preproc_srv = PreprocService()
    sub_analysis_srv = SubjectAnalysisService()
    group_analysis_srv = GroupAnalysisService()

    PLUGIN = 'MultiProc'

    MNI_file = os.path.join(SPMInfo.getinfo()['path'], 'canonical', 'avg152T1.nii')

    def run(self, workflow: Workflow, path: str, nb_procs):

        print(f"[LOG][WORKFLOW] Workflow [{workflow.name}] running...")
        workflow.run(self.PLUGIN, plugin_args={'n_procs': nb_procs})
        print(f"[LOG][WORKFLOW] Workflow [{workflow.name}] results written to [{path}].")

    def build_subject_workflow(self, config: dict, subjects: list, data_descriptor: DataDescriptor, name: str) -> Workflow:

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

        workflow.base_dir = data_descriptor.work_path

        inputs = self.get_subject_input(data_descriptor)

        print(f"[LOG][WORKFLOW][{name}] Connecting subject-level preprocessing nodes...")
        workflow.connect(src_infos, 'subject_id', inputs, 'subject_id')

        gunzip_func = self.get_gunzip('func')
        # inputs -> gunzip_func
        workflow.connect(inputs, 'func',
                         gunzip_func, 'in_file')

        gunzip_anat = self.get_gunzip('anat')
        # inputs -> gunzip_anat
        workflow.connect(inputs, 'anat',
                         gunzip_anat, 'in_file')

        prealign = self.get_prealign()

        # gunzip_func -> prealign (source=func)
        workflow.connect(gunzip_func, 'out_file',
                         prealign, 'source')
        # gunzip_anat -> prealign (target=anat)
        workflow.connect(gunzip_anat, 'out_file',
                         prealign, 'target')

        # prealign -> motion_correction_realignment (func)
        workflow.connect(prealign, 'prealigned_source',
                         nodes['motion_correction_realignment'], SPM.Realign.Input.in_files)

        # distorsion_correction
        # Ignore for now
        # TODO

        if 'slice_timing_correction' in nodes:
            # motion_correction_realignment (func) -> slice_timing_correction (func)
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                             nodes['slice_timing_correction'], SPM.SliceTiming.Input.in_files)

        if "coregistration/source_target/anat_on_func" in features:
            nodes['coregistration'].features.append("coregistration/source_target/anat_on_func")

            # motion_correction_realignment (mean func) -> coregistration (target=func)
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.mean_image,
                             nodes['coregistration'], SPM.Coregister.Input.target)

            # gunzip_anat -> coregistration (source=anat)
            workflow.connect(gunzip_anat, 'out_file',
                             nodes['coregistration'], SPM.Coregister.Input.source)

            # coregistration (source=anat) -> segmentation (anat)
            workflow.connect(nodes['coregistration'], SPM.Coregister.Output.coregistered_source,
                             nodes['segmentation'], SPM.NewSegment.Input.channel_files)

            if 'slice_timing_correction' in nodes:
                # slice_timing_correction (func) -> spatial_normalization (func)
                workflow.connect(nodes['slice_timing_correction'], SPM.SliceTiming.Output.timecorrected_files,
                                 nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)
            else:
                # motion_correction_realignment (func) -> spatial_normalization (func)
                workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                                 nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)

        elif "coregistration/source_target/func_on_anat" in features:
            nodes['coregistration'].features.append("coregistration/source_target/func_on_anat")

            # gunzip_anat -> coregistration (target=anat)
            workflow.connect(gunzip_anat, 'out_file',
                             nodes['coregistration'], SPM.Coregister.Input.target)

            # motion_correction_realignment (mean func) -> coregistration (source=mean func)
            workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.mean_image,
                             nodes['coregistration'], SPM.Coregister.Input.source)

            if 'slice_timing_correction' in nodes:
                # slice_timing_correction (func) -> coregistration (others=func)
                workflow.connect(nodes['slice_timing_correction'], SPM.SliceTiming.Output.timecorrected_files,
                                 nodes['coregistration'], SPM.Coregister.Input.apply_to_files)
            else:
                # motion_correction_realignment (func) -> coregistration (others=func)
                workflow.connect(nodes['motion_correction_realignment'], SPM.Realign.Output.realigned_files,
                                 nodes['coregistration'], SPM.Coregister.Input.apply_to_files)

            # gunzip_anat -> segmentation (anat)
            workflow.connect(gunzip_anat, 'out_file',
                             nodes['segmentation'], SPM.NewSegment.Input.channel_files)

            # coregistration (func) -> spatial_normalization (func)
            workflow.connect(nodes['coregistration'], SPM.Coregister.Output.coregistered_files,
                             nodes['spatial_normalization'], SPM.Normalize.Input.apply_to_files)

        # segmentation -> spatial_normalization
        workflow.connect(nodes['segmentation'], SPM.NewSegment.Output.forward_deformation_field,
                         nodes['spatial_normalization'], SPM.Normalize12.Input.deformation_file)

        # spatial_normalization -> spatial_smoothing
        workflow.connect(nodes['spatial_normalization'], SPM.Normalize12.Output.normalized_files,
                         nodes['spatial_smoothing'], SPM.Smooth.Input.in_files)

        ### SUBJECT LEVEL ANALYSIS ###

        print(f"[LOG][WORKFLOW][{name}] Connecting subject-level analysis nodes...")

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
        # sub_level_model -> output
        workflow.connect(nodes['sub_level_model'], SPM.EstimateModel.Output.mask_image,
                         output,
                         f'{output_path}.@mask_image')
        # sub_level_contrasts -> output
        workflow.connect(nodes['sub_level_contrasts'], SPM.EstimateContrast.Output.spmT_images,
                         output,
                         f'{output_path}.@spmT_images')
        workflow.connect(nodes['sub_level_contrasts'], SPM.EstimateContrast.Output.con_images,
                         output,
                         f'{output_path}.@con_images')

        self.check_implemented_features(workflow, features, name)

        print(f"[LOG][WORKFLOW][{name}] Subject-level workflow ready.")
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

        print(f"[LOG][WORKFLOW][{name}] Connecting group-level analysis nodes...")

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

        print(f"[LOG][WORKFLOW][{name}] Group-level workflow ready.")

        return workflow

    def check_implemented_features(self, workflow, features, name):
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
                f"[LOG][WARNING][Implementation error] [{len(missing_in_features)}] features implemented in workflow [{name}] not present in configuration : [{missing_in_features}]")
        if missing_in_impl_features:
            print(
                f"[LOG][WARNING][Implementation error] [{len(missing_in_impl_features)}] features in configuration not implemented in workflow [{name}] : [{missing_in_impl_features}]")

    def get_infos(self, subjects):
        name = "infos"
        print(f"[LOG][WORKFLOW] Implementing [{name}]...")
        infos = Node(interface=IdentityInterface(fields=['subject_id']), name=name)
        infos.iterables = [('subject_id', subjects)]
        infos.features = ['pipeline']
        print(f"[LOG][WORKFLOW] [{name}] added to workflow")
        return infos

    def get_subject_input(self, data_desc: DataDescriptor):
        name = "subject_input"
        print(f"[LOG][WORKFLOW] Implementing [{name}]...")
        templates = {}
        for key, value in data_desc.input.items():
            templates[key] = os.path.join(data_desc.data_path, value)
        sub_input = Node(interface=SelectFiles(templates, base_directory=data_desc.data_path), name=name)
        print(f"[LOG][WORKFLOW] [{name}] added to workflow")
        return sub_input

    def get_group_input(self, config: str, data_desc: DataDescriptor):
        name = "group_input"
        print(f"[LOG][WORKFLOW] Implementing [{name}]...")
        group_input = Node(
            IdentityInterface(fields=['contrasts']),
            name=name
        )
        contrasts = []
        for subject in data_desc.subjects:
            if subject not in data_desc.no_group_subjects:
                contrasts.append(os.path.join(data_desc.result_path, config, f'_subject_id_{subject}', CONTRAST_NII))
            else:
                print(f"[LOG][WORKFLOW] Subject [{subject}] will be excluded from group analysis")
        group_input.inputs.contrasts = contrasts
        print(f"[LOG][WORKFLOW] [{name}] added to workflow")
        return group_input

    def get_subject_output(self, path: str):
        name = "subject_output"
        print(f"[LOG][WORKFLOW] Implementing [{name}]...")
        datasink = Node(interface=DataSink(base_directory=path), name=name)
        datasink.inputs.regexp_substitutions = [(r'spmT_0001.nii', RESULT_NII)]
        print(f"[LOG][WORKFLOW] [{name}] added to workflow")
        return datasink

    def get_group_output(self, path: str):
        name = "group_output"
        print(f"[LOG][WORKFLOW] Implementing [{name}]...")
        datasink = Node(interface=DataSink(base_directory=path), name=name)
        print(f"[LOG][WORKFLOW] [{name}] added to workflow")
        return datasink

    def get_gunzip(self, type: str):
        name = f'gunzip_{type}'
        print(f"[LOG][WORKFLOW] Implementing [{name}]...")

        def gunzip(in_file):
            import os
            import gzip
            import shutil
            if in_file.endswith('.gz'):
                filename = os.path.basename(in_file[:-3])
                out_file = os.path.abspath(filename)
                if not os.path.exists(out_file):
                    with gzip.open(in_file, 'rb') as f_in:
                        with open(out_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                return out_file
            return os.path.abspath(in_file)

        gz = Node(Function(input_names=['in_file'],
                           output_names=['out_file'],
                           function=gunzip),
                  name=name)
        print(f"[LOG][WORKFLOW] [{name}] added to workflow")
        return gz

    def get_prealign(self):
        def align_centers(source, target):
            from nibabel import Nifti1Image
            from nibabel import save
            import nilearn.image as image
            import numpy as np
            import os

            def get_center(img):
                data = img.get_fdata()
                if len(data.shape) == 4:
                    data = np.mean(data, axis=3)
                affine = img.affine
                indices = np.argwhere(data > np.mean(data))
                v_center = indices.mean(axis=0)
                return affine @ np.append(v_center, 1)

            src_img = image.load_img(source)
            src_center = get_center(src_img)
            tgt_center = get_center(image.load_img(target))
            diff = tgt_center[:3] - src_center[:3]

            new_affine = src_img.affine.copy()
            new_affine[:3, 3] += diff

            out_name = "prealigned_" + os.path.basename(source)
            out_path = os.path.abspath(out_name)

            new_img = Nifti1Image(src_img.get_fdata(), new_affine, src_img.header)
            save(new_img, out_path)

            return out_path

        return Node(
            interface=Function(
                input_names=["source", "target"],
                output_names=["prealigned_source"],
                function=align_centers
            ),
            name="prealign"
        )
