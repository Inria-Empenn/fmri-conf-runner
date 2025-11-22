import nipype.pipeline.engine as pe
from typing import Dict

from nipype import Node
from nipype.interfaces.spm import EstimateModel, EstimateContrast, OneSampleTTestDesign

from core.data_descriptor import DataDescriptor
from core.task_service import TaskService


class GroupAnalysisService:

    task_srv = TaskService()

    steps = [
        'group_level_design',
        'group_level_model',
        'group_level_contrasts'
    ]

    def get_nodes(self, features: list, data_desc: DataDescriptor) -> Dict[str, Node]:
        print("Implementing group level analysis nodes...")
        nodes = {}
        for step in self.steps:
            print(f"Implementing [{step}]...")
            node = self.get_node(step, features, data_desc)
            if node:
                nodes[step] = node
            print(f"[{step}] added to workflow")

        return nodes

    def get_node(self, name, features: list, data_desc: DataDescriptor):
        if name == 'group_level_design':
            return self.get_design()
        if name == 'group_level_model':
            return self.get_model()
        if name == 'group_level_contrasts':
            return self.get_contrasts(data_desc)

    def get_design(self):
        return pe.Node(interface=OneSampleTTestDesign(), name='group_level_design')

    def get_model(self):
        estimate = Node(interface=EstimateModel(), name="group_level_model")
        estimate.inputs.estimation_method = {'Classical': 1}
        estimate.inputs.write_residuals = True
        return estimate

    def get_contrasts(self, data_desc):
        contrast = pe.Node(interface=EstimateContrast(), name="group_level_contrasts")
        contrast.inputs.contrasts = [('Group', 'T', ['mean'], [1])]
        contrast.inputs.group_contrast = True
        return contrast