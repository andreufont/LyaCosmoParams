import os
import sys
import json
import configargparse
from shutil import copy
import read_gadget
import write_submit_genpk_dirac as wsd

""" Script to run the genpk stage of the postprocessing
for a single simulation """

sample="nu"
time='20:00:00'

pair_dir="/share/rcifdata/chrisp/emulator_768_09122019/sim_pair_h"
print('writing scripts for pair in',pair_dir)

for sim in ['sim_plus','sim_minus']:
    wsd.write_genpk_scripts_in_sim(simdir=pair_dir+'/'+sim,
                                    time=time,verbose=True)

