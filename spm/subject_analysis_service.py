import nipype.pipeline.engine as pe  # pypeline engine
from nipype import Node, Function
from nipype.algorithms.modelgen import SpecifySPMModel
from nipype.interfaces.spm import EstimateModel, Level1Design, EstimateContrast
from typing import Dict

from core.data_descriptor import DataDescriptor
from core.task_service import TaskService


class SubjectAnalysisService:
    task_srv = TaskService()

    steps = [
        'sub_level_spec',
        'sub_level_design',
        'sub_level_model',
        'sub_level_contrasts',
        'sub_level_spec_realignment_parameters'
    ]

    def get_nodes(self, features: list, data_desc: DataDescriptor) -> Dict[str, Node]:

        print("Implementing subject level analysis nodes...")
        nodes = {}
        for step in self.steps:
            if step == 'sub_level_spec_realignment_parameters':
                if f"signal_modeling/nuisance_regressors" not in features:
                    continue
            print(f"Implementing [{step}]...")
            node = self.get_node(step, features, data_desc)
            if node:
                nodes[step] = node
            print(f"[{step}] added to workflow")

        return nodes

    def get_node(self, name, features: list, data_desc: DataDescriptor):
        if name == 'sub_level_spec':
            return self.get_model_spec(data_desc)
        if name == 'sub_level_design':
            return self.get_design(features, data_desc)
        if name == 'sub_level_model':
            return self.get_model()
        if name == 'sub_level_contrasts':
            return self.get_contrasts(data_desc)
        if name == 'sub_level_spec_realignment_parameters':
            return self.get_realignment_parameters(features)

    def get_model_spec(self, data_desc: DataDescriptor):
        modelspec = Node(interface=SpecifySPMModel(), name="sub_level_spec")
        modelspec.inputs.concatenate_runs = False
        modelspec.inputs.input_units = data_desc.units
        modelspec.inputs.output_units = data_desc.units
        modelspec.inputs.time_repetition = data_desc.tr
        modelspec.inputs.high_pass_filter_cutoff = 128
        return modelspec

    def get_design(self, features: list, data_desc: DataDescriptor):
        design = pe.Node(interface=Level1Design(), name="sub_level_design")
        design.inputs.timing_units = data_desc.units
        design.inputs.interscan_interval = data_desc.tr

        name = "signal_modeling"

        if f"{name}/hrf" in features:
            time = 0
            dispersion = 0
            if f"{name}/hrf/temporal_derivs" in features:
                time = 0
                dispersion = 0
            if f"{name}/hrf/temporal_derivs" in features:
                time = 1
            if f"{name}/hrf/temporal_dispersion_derivs" in features:
                time = 1
                dispersion = 1
            design.inputs.bases = {'hrf': {'derivs': [time, dispersion]}}

        if f"{name}/temporal_noise_autocorrelation" in features:
            if f"{name}/temporal_noise_autocorrelation/AR1" in features:
                design.inputs.model_serial_correlations = 'AR(1)'
            if f"{name}/temporal_noise_autocorrelation/FAST" in features:
                design.inputs.model_serial_correlations = 'FAST'

        design.inputs.mask_threshold = 0.8
        design.inputs.volterra_expansion_order = 1
        return design

    def get_model(self):
        estimate = Node(interface=EstimateModel(), name="sub_level_model")
        estimate.inputs.estimation_method = {'Classical': 1}
        estimate.inputs.write_residuals = True
        return estimate

    def get_contrasts(self, data_desc: DataDescriptor):
        contrast = pe.Node(interface=EstimateContrast(), name="sub_level_contrasts")
        contrast.inputs.contrasts = self.task_srv.get_task_contrasts(data_desc.task)
        return contrast

    def get_realignment_parameters(self, features):
        name = "signal_modeling/nuisance_regressors"

        def get_motions_files(realignment_parameters, nb_regressors):
            import numpy as np
            output_file = f"{realignment_parameters}.done"
            motion = np.loadtxt(realignment_parameters)
            if nb_regressors == 6:
                expanded = motion
            elif nb_regressors == 18:
                derivatives = np.diff(motion, axis=0, prepend=0)
                expanded = np.column_stack((motion, derivatives, motion ** 2))
            elif nb_regressors == 24:
                derivatives = np.diff(motion, axis=0, prepend=0)
                squared_derivatives = derivatives ** 2
                expanded = np.column_stack((motion, derivatives, motion ** 2, squared_derivatives))
            else:
                raise ValueError(f"[{nb_regressors}] regressors not implemented")
            np.savetxt(output_file, expanded)
            return output_file

        nuisance_regressors = pe.Node(interface=Function(
            input_names=['realignment_parameters', 'nb_regressors'],
            output_names=['realignment_parameters'],
            function=get_motions_files
        ),
            name='sub_level_spec_realignment_parameters'
        )
        nuisance_regressors.inputs.nb_regressors = float(self.get_feature_end(f"{name}/motion", features))
        return nuisance_regressors

    def get_feature_end(self, prefix, features):
        for feature in features:
            if feature.startswith(prefix + '/'):
                return feature[len(prefix + '/'):]
        return ""
