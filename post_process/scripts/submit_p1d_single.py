import os
import sys
import json
from shutil import copy
import read_gadget
import write_submit_p1d_dirac as wsd

""" Script to run the p1d calculation stage of the postprocessing
for a single simulation """

n_skewers = 500
width_Mpc = 0.05
zmax = 6.0
scales_tau = '1.0'
time = '10:00:00'
run = True
p1d_label="p1d"
verbose=True

# full path to folder for this particular simulation pair
pair_dir="/share/rcifdata/chrisp/emulator_768_09122019/sim_pair_29"

if verbose:
    print('writing scripts for pair in',pair_dir)

for sim in ['sim_plus','sim_minus']:
    wsd.write_p1d_scripts_in_sim(simdir=pair_dir+'/'+sim,
            n_skewers=n_skewers,width_Mpc=width_Mpc,
            scales_tau=scales_tau,
            time=time,zmax=zmax,
            verbose=verbose,p1d_label=p1d_label,run=run)

