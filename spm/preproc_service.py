import os

from nipype import Node
from nipype.interfaces.spm import Smooth, Coregister, NewSegment, SliceTiming, Normalize12, Realign
from nipype.interfaces.spm.base import Info as SPMInfo
from typing import Dict

from core.data_descriptor import DataDescriptor


class PreprocService:
    steps = [
        'distorsion_correction',
        'motion_correction_realignment',
        'slice_timing_correction',
        'coregistration',
        'segmentation',
        'spatial_normalization',
        'spatial_smoothing'
    ]

    bias_regs = {
        'extremely_light': 0.00001,
        'very_light': 0.0001,
        'light': 0.001,
        'medium': 0.01,
        'heavy': 0.1
    }

    cost_funcs = {
        'mutual_information': 'mi',
        'normalised_mutual_information': 'nmi',
        'entropy_correlation_coefficient': 'ecc',
        'normalised_cross_correlation': 'ncc'
    }

    interpolation = {
        "nearest_neighbour" : 0,
        "trilinear" : 1,
        "bspline": 4
    }

    tool = 'spm'

    tpm_file = os.path.join(SPMInfo.getinfo()['path'], 'tpm', 'TPM.nii')

    def get_nodes(self, features: list, data_desc: DataDescriptor) -> Dict[str, Node]:
        print("Implementing preprocessing nodes...")
        nodes = {}
        for step in self.steps:
            if step in features:
                print(f"Implementing [{step}]...")
                node = self.get_node(step, features, data_desc)
                if node:
                    nodes[step] = node
                print(f"[{step}] added to workflow")

        return nodes

    def get_node(self, name, features: list, data_desc: DataDescriptor):
        if name == 'distorsion_correction':
            return self.get_distorsion_correction(features)
        if name == 'motion_correction_realignment':
            return self.get_motion_correction_realignment(features)
        if name == 'slice_timing_correction':
            return self.get_slice_timing_correction(features, data_desc)
        if name == 'coregistration':
            return self.get_coregistration(features)
        if name == 'segmentation':
            return self.get_segmentation(features)
        if name == 'spatial_normalization':
            return self.get_spatial_normalization(features)
        if name == 'spatial_smoothing':
            return self.get_smoothing(features)

    def get_motion_correction_realignment(self, features: list):

        name = "motion_correction_realignment"
        node = Node(interface=Realign(), name=name)
        node.features = [name, f'{name}/tool', f'{name}/tool/{self.tool}']

        if f"{name}/register_to" in features:
            node.features.append(f"{name}/register_to")
            if f"{name}/register_to/first" in features:
                node.inputs.register_to_mean = False
                node.features.append(f"{name}/register_to/first")

            if f"{name}/register_to/mean" in features:
                node.inputs.register_to_mean = True
                node.features.append(f"{name}/register_to/mean")
        return node

    def get_slice_timing_correction(self, features: list, data_desc: DataDescriptor):
        name = "slice_timing_correction"
        node = Node(interface=SliceTiming(), name=name)
        node.features = [name, f'{name}/tool', f'{name}/tool/{self.tool}']
        node.inputs.num_slices = data_desc.slices_nb
        node.inputs.time_repetition = data_desc.tr
        node.inputs.time_acquisition = data_desc.tr - (data_desc.tr / data_desc.slices_nb)
        node.inputs.slice_order = list(range(data_desc.slices_nb, 0, -1))  # [64 63 62 ... 3 2 1]

        if f"{name}/ref_slice" in features:
            node.features.append(f"{name}/ref_slice")
            if f"{name}/ref_slice/first" in features:
                node.inputs.ref_slice = 1
                node.features.append(f"{name}/ref_slice/first")

            if f"{name}/ref_slice/middle" in features:
                node.inputs.ref_slice = data_desc.slices_nb / 2
                node.features.append(f"{name}/ref_slice/middle")

        return node

    def get_coregistration(self, features: list):
        name = "coregistration"
        node = Node(interface=Coregister(), name=name)
        node.features = [name, f'{name}/tool', f'{name}/tool/{self.tool}']
        node.features.append(f"{name}/cost_function")
        function = self.get_feature_end(f"{name}/cost_function", features)
        node.features.append(f"{name}/cost_function/{function}")
        node.inputs.cost_function = self.cost_funcs[function]
        node.features.append(f"{name}/source_target")
        return node

    def get_segmentation(self, features: list):
        name = "segmentation"
        node = Node(interface=NewSegment(), name=name)
        node.features = [name, f'{name}/tool', f'{name}/tool/{self.tool}']
        tissue1 = (self.tpm_file, 1), 1, (True, False), (False, False)
        tissue2 = (self.tpm_file, 2), 1, (True, False), (False, False)
        tissue3 = (self.tpm_file, 3), 2, (True, False), (False, False)
        tissue4 = (self.tpm_file, 4), 3, (True, False), (False, False)
        tissue5 = (self.tpm_file, 5), 4, (True, False), (False, False)
        tissue6 = (self.tpm_file, 6), 2, (False, False), (False, False)
        node.inputs.tissues = [tissue1, tissue2, tissue3, tissue4, tissue5, tissue6]
        node.inputs.write_deformation_fields = [False, True]
        return node

    def get_spatial_normalization(self, features: list):
        name = "spatial_normalization"
        node = Node(interface=Normalize12(), name=name)
        node.features = [name, f'{name}/tool', f'{name}/tool/{self.tool}']

        # unique template for SPM
        node.features.append(f'{name}/template')
        node.features.append(f'{name}/template/Ixi549Space')

        # uniaue algo for SPM
        node.features.append(f'{name}/algorithm')
        node.features.append(f'{name}/algorithm/nonlinear')

        node.inputs.jobtype = 'write'

        if f"{name}/bias_regularisation" in features:
            node.features.append(f"{name}/bias_regularisation")
            bias = self.get_feature_end(f"{name}/bias_regularisation", features)
            node.inputs.bias_regularization = self.bias_regs[bias]
            node.features.append(f"{name}/bias_regularisation/{bias}")
        else:
            node.inputs.bias_regularization = 0

        if f"{name}/bias_fwhm" in features:
            node.features.append(f"{name}/bias_fwhm")
            fwhm = self.get_feature_end(f"{name}/bias_fwhm", features)
            node.inputs.bias_fwhm = float(fwhm)
            node.features.append(f"{name}/bias_fwhm/{fwhm}")
        else:
            node.inputs.bias_fwhm = "Inf"

        if f"{name}/interpolation" in features:
            node.features.append(f"{name}/interpolation")
            function = self.get_feature_end(f"{name}/interpolation", features)
            node.inputs.write_interp = self.interpolation[function]
            node.features.append(f"{name}/interpolation/{function}")
        return node

    def get_smoothing(self, features: list):
        name = "spatial_smoothing"
        node = Node(interface=Smooth(), name=name)
        node.features = [name, f'{name}/tool', f'{name}/tool/{self.tool}']
        node.inputs.fwhm = 0
        if f"{name}/fwhm" in features:
            node.features.append(f"{name}/fwhm")
            fwhm = self.get_feature_end(f"{name}/fwhm", features)
            node.inputs.fwhm = float(fwhm)
            node.features.append(f"{name}/fwhm/{fwhm}")
        return node

    def get_feature_end(self, prefix, features):
        for feature in features:
            if feature.startswith(prefix + '/'):
                return feature[len(prefix + '/'):]
        return ""

    def get_distorsion_correction(self, features):
        return None
