import numpy as np
import sys
import os
import json
import matplotlib.pyplot as plt
import matplotlib as mpl
import cProfile
import emcee
import corner
# our own modules
import simplest_emulator
import linear_emulator
import gp_emulator
import data_PD2013
import mean_flux_model
import thermal_model
import pressure_model
import lya_theory
import likelihood
import emcee_sampler
import data_MPGADGET
import z_emulator
import p1d_arxiv

test_sim_number=50

# read P1D measurement
#z_list=np.array([2.0,2.75,3.25,4.0])
data=data_MPGADGET.P1D_MPGADGET(sim_number=test_sim_number)
zs=data.z

repo=os.environ['LYA_EMU_REPO']
skewers_label='Ns256_wM0.05'
#skewers_label=None
basedir=repo+"/p1d_emulator/sim_suites/emulator_256_28082019/"
#basedir=repo+"/p1d_emulator/sim_suites/emulator_256_15072019/"
p1d_label=None
undersample_z=1
paramList=["mF","sigT_Mpc","gamma","kF_Mpc","Delta2_p","n_p"]
max_arxiv_size=None
kmax_Mpc=8

archive=p1d_arxiv.ArxivP1D(basedir=basedir,
                            drop_tau_rescalings=True,z_max=4,
                            drop_sim_number=test_sim_number,
                            drop_temp_rescalings=True,skewers_label=skewers_label,
                            undersample_cube=8)
emu=z_emulator.ZEmulator(basedir,p1d_label,skewers_label,
                                max_arxiv_size=max_arxiv_size,z_max=4,
                                verbose=False,paramList=paramList,train=True,
                                emu_type="k_bin",passArxiv=archive,checkHulls=False,
                                drop_tau_rescalings=True,
                                drop_temp_rescalings=True)
'''
emu=gp_emulator.GPEmulator(basedir,p1d_label,skewers_label,
                                max_arxiv_size=max_arxiv_size,z_max=4,
                                passArxiv=archive,
                                verbose=False,paramList=paramList,train=True,
                                emu_type="k_bin", checkHulls=False,
                                drop_tau_rescalings=True,
                                drop_temp_rescalings=True)
'''
free_param_names=['mF',"Delta2_p","sigT_Mpc","gamma","kF_Mpc","n_p"]

like=likelihood.simpleLikelihood(data=data,emulator=emu,
                            free_param_names=free_param_names,verbose=False,
                            prior_Gauss_rms=0.15)

like.plot_p1d()

sampler = emcee_sampler.EmceeSampler(like=like,
                        free_param_names=free_param_names,verbose=True,
                        nwalkers=20)


for p in sampler.like.free_params:
    print(p.name,p.value,p.min_value,p.max_value)


sampler.like.go_silent()
sampler.store_distances=True
sampler.run_burn_in(nsteps=100)
#sampler.run_chains(nsteps=200)
'''
plt.figure()
for aa,array in enumerate(sampler.distances):
    plt.hist(array,label="z=%.2f" % sampler.like.theory.zs[aa],alpha=0.5,bins=300)

plt.xlabel("Euclidean distance to nearest training point")
plt.ylabel("Counts")
plt.legend()
plt.show()
'''

sampler.run_chains(nsteps=1000)
print("Mean acceptance fraction: {0:.3f}".format(np.mean(sampler.sampler.acceptance_fraction)))

sampler.plot_corner(cube=False,mock_values=True)
sampler.plot_best_fit()
sampler.write_chain_to_file()
