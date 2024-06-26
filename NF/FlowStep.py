import torch
from torch import nn as nn

from NF import ActNorms, Permutations, AffineCouplings

class FlowStep(nn.Module):
    def __init__(self, in_channels, cond_channels=None, flow_actNorm='actNorm1d', flow_permutation='invconv', flow_coupling='Affine', LRvsothers=True,
                 actnorm_scale=1.0, LU_decomposed=False):
        super().__init__()
        self.flow_actNorm = flow_actNorm
        self.flow_permutation = flow_permutation
        self.flow_coupling = flow_coupling

        # 1. actnorm
        if self.flow_actNorm == 'actNorm1d':
            self.actnorm = ActNorms.ActNorm1d(in_channels, actnorm_scale)
        elif self.flow_actNorm == "none":
            self.actnorm = None

        # 2. permute # todo: maybe hurtful for downsampling; presever the structure of downsampling
        if self.flow_permutation == "invconv":
            self.permute = Permutations.InvertibleConv1x1(in_channels, LU_decomposed=LU_decomposed)
        elif self.flow_permutation == "none":
            self.permute = None

        # 3. coupling
        if self.flow_coupling == "Affine":
            self.affine = AffineCouplings.AffineCoupling(in_channels=in_channels, cond_channels=cond_channels)
        
    def forward(self, z, u=None, logdet=None, reverse=False):
        if not reverse:
            return self.normal_flow(z, u, logdet)
        else:
            return self.reverse_flow(z, u, logdet)

    def normal_flow(self, z, u=None, logdet=None):
        # 1. actnorm
        if self.actnorm is not None:
            z, logdet = self.actnorm(z, logdet=logdet, reverse=False)
        # 2. permute
        if self.permute is not None:
            z, logdet = self.permute(z, logdet=logdet, reverse=False)
        # 3. coupling
        z, logdet = self.affine(z, u=u, logdet=logdet, reverse=False)
        return z, logdet

    def reverse_flow(self, z, u=None, logdet=None):
        # 1.coupling
        z, logdet = self.affine(z, u=u, logdet=logdet, reverse=True)
        # 2. permute
        if self.permute is not None:
            z, logdet = self.permute(z, logdet=logdet, reverse=True)
        # 3. actnorm
        if self.actnorm is not None:
            z, logdet = self.actnorm(z, logdet=logdet, reverse=True)
        return z, logdet

