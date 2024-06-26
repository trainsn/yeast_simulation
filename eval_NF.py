# main file

from __future__ import absolute_import, division, print_function

import os
import argparse
import math
import time

import numpy as np
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from yeast import *
from NF.FlowNet_surrogate import ParamFlowNetCond
import loss_helper
import utils

import pdb

# parse arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Deep Learning Model")

    parser.add_argument("--no-cuda", action="store_true", default=False,
                        help="disables CUDA training")
    parser.add_argument("--data-parallel", action="store_true", default=False,
                        help="enable data parallelism")

    parser.add_argument("--resume", type=str, default="",
                        help="path to the latest checkpoint (default: none)")

    parser.add_argument("--K", type=int, default=3,
                        help="the number of unconditional transformations")
    parser.add_argument("--K_cond", type=int, default=3,
                        help="the number of conditional transformations")

    parser.add_argument("--sn", action="store_true", default=False,
                        help="enable spectral normalization")

    parser.add_argument("--lr", type=float, default=1e-3,
                        help="learning rate (default: 1e-3)")
    parser.add_argument("--beta1", type=float, default=0.9,
                        help="beta1 of Adam (default: 0.9)")
    parser.add_argument("--beta2", type=float, default=0.999,
                        help="beta2 of Adam (default: 0.999)")
    parser.add_argument("--start-epoch", type=int, default=0,
                        help="start epoch number (default: 0)")
    parser.add_argument("--n-samples", type=int, default=10,
                        help="number of samples run for the dropout or ensemble model")
    
    parser.add_argument("--id", type=int, default=0,
                        help="instance id in the testing set")

    return parser.parse_args()

# the main function
def main(args):
    # log hyperparameters
    print(args)

    # select device
    args.cuda = not args.no_cuda and torch.cuda.is_available()
    device = torch.device("cuda:0" if args.cuda else "cpu")

    # model
    def weights_init(m):
        if isinstance(m, nn.Linear):
            nn.init.xavier_normal_(m.weight)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Conv1d):
            nn.init.xavier_normal_(m.weight)
            if m.bias is not None:
                nn.init.zeros_(m.bias)

    def add_sn(m):
        for name, c in m.named_children():
            m.add_module(name, add_sn(c))
        if isinstance(m, (nn.Linear, nn.Conv1d)):
            return nn.utils.spectral_norm(m, eps=1e-4)
        else:
            return m

    g_model = ParamFlowNetCond(C=1, K=args.K, K_cond=args.K_cond)
    # if args.sn:
    #     g_model = add_sn(g_model)

    g_model.to(device)

    mse_criterion = nn.MSELoss(reduction='none')

    # optimizer
    g_optimizer = optim.Adam(g_model.parameters(), lr=args.lr,
                             betas=(args.beta1, args.beta2))

    # load checkpoint
    if args.resume:
        if os.path.isfile(args.resume):
            print("=> loading checkpoint {}".format(args.resume))
            checkpoint = torch.load(args.resume, map_location=torch.device(device))
            args.start_epoch = checkpoint["epoch"]
            g_model.load_state_dict(checkpoint["g_model_state_dict"])
            g_optimizer.load_state_dict(checkpoint["g_optimizer_state_dict"])
            print("=> loaded checkpoint {} (epoch {})"
                    .format(args.resume, checkpoint["epoch"]))
            
    params, C42a_data, sample_weight, dmin, dmax  = ReadYeastDataset(active=False)
    params, C42a_data, sample_weight = torch.from_numpy(params).float().to(device), torch.from_numpy(C42a_data).float().to(device), torch.from_numpy(sample_weight).float().to(device)
    train_split = torch.from_numpy(np.load('train_split.npy'))
    test_params, test_C42a_data = params[~train_split], C42a_data[~train_split]

    # testing...
    g_model.train()
    with torch.no_grad():
        start_time = time.time()  # Start timing
        fake_data = [] 
        for _ in range(args.n_samples):
            tmp, _, _ = g_model.sample(dummy_z=None, d_param=test_params, eps_std=0.8)
            fake_data.append(tmp)
        fake_data = torch.stack(fake_data, dim=0)
        mu = torch.mean(fake_data, dim=0)[:, 0]
        var = torch.std(fake_data, dim=0)[:, 0]
        end_time = time.time()  # End timing
        all_mse = mse_criterion(test_C42a_data, mu)
        all_mse /= (696.052 / dmax) ** 2
        mse = all_mse.mean().item()
        nll = loss_helper.Gaussian_NLL(test_C42a_data, mu, var, reduce=False)
        print(f"NLL: {nll.median().item():.2f}")

        mu = ((mu + 1) * (dmax - dmin) / 2) + dmin
        var = var * (dmax - dmin) / 2

        fake_data = ((fake_data + 1) * (dmax - dmin) / 2) + dmin
        psnr = 20. * np.log10(2.) - 10. * np.log10(mse)
        print(f"PSNR: {psnr:.2f} dB")
        total_time = end_time - start_time
        print(f"Total evaluation time: {total_time:.4f} seconds")   

        # Rescale data back to original range
        test_C42a_data = ((test_C42a_data + 1) * (dmax - dmin) / 2) + dmin

    if args.id >= 0:
        example_test = test_C42a_data[args.id].cpu().numpy()
        example_mu = mu[args.id].cpu().numpy()
        example_var = var[args.id].cpu().numpy()
        # example_var = np.minimum(example_var, np.percentile(example_var, 90))

        utils.render_one_circle("Ensemble", "Aleatoric", args.id, example_test, example_mu, example_var)

if __name__ == "__main__":
    main(parse_args())
