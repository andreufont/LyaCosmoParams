import os
import sys
import json
import configargparse
from shutil import copy
import read_gadget
import write_submit_skewers_dirac as wsd

""" Script to run the flux skewer generation stage of the postprocessing
for a single simulation """

scales_T0='1.0'
scales_gamma='1.0'
n_skewers=500
width_Mpc=0.05
time='22:00:00'
zmax=6

verbose=True

pair_dir="/share/rcifdata/chrisp/emulator_768_09122019/sim_pair_h"

if verbose:
    print('writing scripts for pair in',pair_dir)

for sim in ['sim_plus','sim_minus']:
    wsd.write_skewer_scripts_in_sim(simdir=pair_dir+'/'+sim,
            n_skewers=n_skewers,width_Mpc=width_Mpc,
            scales_T0=scales_T0,scales_gamma=scales_gamma,
            time=time,zmax=zmax,
            verbose=verbose,run=True)

