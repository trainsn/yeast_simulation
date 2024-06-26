# Residual block architecture

import torch
import torch.nn as nn
from torch.nn import functional as F

import pdb

class BasicBlockGenerator(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1,
                             padding=1, activation=F.relu, upsample=True):
        super(BasicBlockGenerator, self).__init__()

        self.activation = activation
        self.upsample = upsample
        self.conv_res = None
        if self.upsample or in_channels != out_channels:
            self.conv_res = nn.Conv1d(in_channels, out_channels,
                1, 1, 0, bias=False, padding_mode='circular')

        self.in0 = nn.InstanceNorm1d(in_channels)
        self.conv0 = nn.Conv1d(in_channels, out_channels, kernel_size,
            stride, padding, bias=False, padding_mode='circular')

        self.in1 = nn.InstanceNorm1d(out_channels)
        self.conv1 = nn.Conv1d(out_channels, out_channels, kernel_size,
            stride, padding, bias=False, padding_mode='circular')

    def forward(self, x):
        residual = x
        if self.upsample:
            residual = F.interpolate(residual, scale_factor=2)
        if self.conv_res:
            residual = self.conv_res(residual)

        out = self.in0(x)
        out = self.activation(out)
        if self.upsample:
            out = F.interpolate(out, scale_factor=2)
        out = self.conv0(out)

        out = self.in1(out)
        out = self.activation(out)
        out = self.conv1(out)

        return out + residual