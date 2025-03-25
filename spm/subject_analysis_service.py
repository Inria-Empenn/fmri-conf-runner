import nipype.pipeline.engine as pe  # pypeline engine
from nipype import Node
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
        'sub_level_estimate',
        'sub_level_contrasts'
    ]

    def get_nodes(self, features: list, data_desc: DataDescriptor) -> Dict[str, Node]:
        nodes = {}

        for step in self.steps:
            print(f"Implementing [{step}]...")
            node = self.get_node(step, features, data_desc)
            if node:
                nodes[step] = node
            print(f"[{step}] added to workflow")

        return nodes

    def get_node(self, name, features: list, data_desc: DataDescriptor):
        if name ==  'sub_level_spec':
            return self.get_model_spec(data_desc)
        if name ==  'sub_level_design':
            return self.get_design(features, data_desc)
        if name ==  'sub_level_estimate':
            return self.get_estimate()
        if name ==  'sub_level_contrasts':
            return self.get_contrasts(data_desc)

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

    def get_estimate(self):
        estimate = pe.Node(interface=EstimateModel(), name="sub_level_estimate")
        estimate.inputs.estimation_method = {'Classical': 1}
        estimate.inputs.write_residuals = True
        return estimate

    def get_contrasts(self, data_desc: DataDescriptor):
        contrast = pe.Node(interface=EstimateContrast(), name="sub_level_contrasts")
        contrast.inputs.contrasts = self.task_srv.get_task_contrasts(data_desc.task)
        return contrast