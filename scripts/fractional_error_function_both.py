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

n_points=5000
mF_res=False
temp_res=False
# read P1D measurement
z_list=np.array([2.0,2.75,3.25,4.0])
data=data_MPGADGET.P1D_MPGADGET(z_list=z_list,filename="1024_mock_0.json")
data._cull_data(0.0075)
zs=data.z

k_mpc=data.k*80

tau_values=[data.like_params["ln_tau_1"],data.like_params["ln_tau_0"]]
gamma_values=[data.like_params["ln_gamma_1"],data.like_params["ln_gamma_0"]]
T0_values=[data.like_params["T0_1"],data.like_params["T0_2"],data.like_params["T0_3"]]
kF_values=[data.like_params["ln_kF_1"],data.like_params["ln_kF_0"]]


mf_model=mean_flux_model.MeanFluxModel(ln_tau_coeff=tau_values)
thermal_model=thermal_model.ThermalModel(ln_gamma_coeff=gamma_values,
                                ln_T0_coeff=T0_values)
kF_model=pressure_model.PressureModel(ln_kF_coeff=kF_values)

repo=os.environ['LYA_EMU_REPO']
skewers_label='Ns256_wM0.05'
#skewers_label=None
basedir=repo+"/p1d_emulator/sim_suites/emulator_256_28082019/"

#basedir=repo+"/p1d_emulator/sim_suites/emulator_256_15072019/"
p1d_label=None
undersample_z=1
paramList=["mF","sigT_Mpc","gamma","kF_Mpc","Delta2_p"]
max_arxiv_size=None
kmax_Mpc=8


emu=z_emulator.ZEmulator(basedir,p1d_label,skewers_label,
                                max_arxiv_size=max_arxiv_size,z_max=4,
                                verbose=False,paramList=paramList,train=True,
                                emu_type="polyfit",z_list=z_list,
                                drop_tau_rescalings=True,
                                drop_temp_rescalings=True)


emu_full=gp_emulator.GPEmulator(basedir,p1d_label,skewers_label,
                                max_arxiv_size=max_arxiv_size,z_max=4,
                                verbose=False,paramList=paramList,train=True,
                                emu_type="polyfit",z_list=z_list,
                                drop_tau_rescalings=True,
                                drop_temp_rescalings=True)

k_point=k_mpc[5]

plt.figure()
for aa, emulator in enumerate(emu.emulators):
    ## Set up min/max prior volume
    limits={}
    for param in paramList:
        par_values=emulator.arxiv.get_param_values(param)
        limits[param]=np.array([min(par_values),max(par_values)])
    ## Randomly sample prior volume and get fractional error
    pred_dict={}
    distances=np.empty(n_points)
    frac_error=np.empty(n_points)
    for bb in range(n_points):
        for param in paramList:
            pred_dict[param]=np.random.uniform(limits[param][0],limits[param][1])
        distances[bb]=emulator.get_nearest_distance(pred_dict)
        p1d,error=emulator.emulate_p1d_Mpc(pred_dict,k_point,return_covar=True)
        frac_error[bb]=error/p1d
    sigma_rbf=emulator.gp.param_array[1]
    sigma_linear=emulator.gp.param_array[0]
    lengthscale=emulator.gp.param_array[2]
    ## Plot scatter
    plt.scatter(distances,frac_error,s=2,label=r"z=%.2f, $\sigma^2_\mathrm{RBF}=%.3f$, $\sigma^2_\mathrm{linear}=%.3f$, $l_\mathrm{RBF}=%.3f$" % (emu.zs[aa],sigma_rbf,sigma_linear,lengthscale))

distances=np.empty(n_points)
frac_error=np.empty(n_points)
for bb in range(n_points):
    for param in paramList:
        pred_dict[param]=np.random.uniform(limits[param][0],limits[param][1])
    distances[bb]=emulator.get_nearest_distance(pred_dict)
    p1d,error=emulator.emulate_p1d_Mpc(pred_dict,k_point,return_covar=True)
    frac_error[bb]=error/p1d
sigma_rbf=emulator.gp.param_array[1]
sigma_linear=emulator.gp.param_array[0]
lengthscale=emulator.gp.param_array[2]
plt.scatter(distances,frac_error,s=2,label=r"All points, $\sigma^2_\mathrm{RBF}=%.3f$, $\sigma^2_\mathrm{linear}=%.3f$, $l_\mathrm{RBF}=%.3f$" % (sigma_rbf,sigma_linear,lengthscale),color="black")
plt.title(r"$\bar{F}$ rescalings = %s, temp rescalings = %s" % (mF_res, temp_res))
plt.ylabel("Fractional error")
plt.legend(loc="upper left",markerscale=2.5)
plt.xlabel("Euclidean distance to nearest training point")
plt.tight_layout()
plt.legend()
plt.show()