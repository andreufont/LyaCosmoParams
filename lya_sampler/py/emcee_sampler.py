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
import z_emulator
import data_PD2013
import mean_flux_model
import thermal_model
import lya_theory
import likelihood
import likelihood_parameter
import scipy.stats
import p1d_arxiv
import data_MPGADGET


class EmceeSampler(object):
    """Wrapper around an emcee sampler for Lyman alpha likelihood"""

    def __init__(self,like=None,emulator=None,free_parameters=None,
                        nwalkers=None,read_chain_file=None,verbose=False):
        """Setup sampler from likelihood, or use default.
            If read_chain_file is provided, read pre-computed chain."""

        self.verbose=verbose
        self.store_distances=False

        if read_chain_file:
            if self.verbose: print('will read chain from file',read_chain_file)
            self.read_chain_from_file(read_chain_file)
            self.nwalkers=None
            self.sampler=None
            self.p0=None
        else: 
            if like:
                if self.verbose: print('use input likelihood')
                self.like=like
                if free_parameters:
                    self.like.set_free_parameters(free_parameters)
            else:
                if self.verbose: print('use default likelihood')
                data=data_PD2013.P1D_PD2013(blind_data=True)
                zs=data.z
                theory=lya_theory.LyaTheory(zs,emulator=emulator)
                self.like=likelihood.Likelihood(data=data,theory=theory,
                                free_parameters=free_parameters,verbose=False)
            # number of free parameters to sample
            self.ndim=len(self.like.free_params)
            self.chain_from_file=None
            # number of walkers
            if nwalkers:
                self.nwalkers=nwalkers
            else:
                self.nwalkers=10*self.ndim
            if self.verbose: print('setup with',self.nwalkers,'walkers')
            # setup sampler
            self.sampler = emcee.EnsembleSampler(self.nwalkers,self.ndim,
                                                            self.log_prob)
            # setup walkers
            self.p0=self.get_initial_walkers()

        '''
        if like:
            if self.verbose: print('use input likelihood')
            self.like=like
            if free_parameters:
                self.like.set_free_parameters(free_parameters)
        else:
            if self.verbose: print('use default likelihood')
            data=data_PD2013.P1D_PD2013(blind_data=True)
            zs=data.z
            theory=lya_theory.LyaTheory(zs,emulator=emulator)
            self.like=likelihood.Likelihood(data=data,theory=theory,
                            free_parameters=free_parameters,verbose=False)
        '''

        self.gr_convergence=[[],[]]

        self.distances=[]
        for aa in range(len(self.like.data.z)):
            self.distances.append([])

        if self.verbose:
            print('done setting up sampler')
        

    def run_burn_in(self,nsteps,nprint=20):
        """Start sample from initial points, for nsteps"""

        if not self.sampler: raise ValueError('sampler not properly setup')

        if self.verbose: print('start burn-in, will do',nsteps,'steps')

        pos=self.p0
        for i,result in enumerate(self.sampler.sample(pos,iterations=nsteps)):
            pos=result[0]
            if self.verbose and (i % nprint == 0):
                print(i,np.mean(pos,axis=0))

        if self.verbose: print('finished burn-in')

        self.burnin_nsteps=nsteps
        self.burnin_pos=pos
    
        return


    def run_chains(self,nsteps,nprint=20):
        """Run actual chains, starting from end of burn-in"""

        if not self.sampler: raise ValueError('sampler not properly setup')

        # reset and run actual chains
        self.sampler.reset()

        pos=self.burnin_pos
        for i, result in enumerate(self.sampler.sample(pos,iterations=nsteps)):
            if (i % nprint == 0) and (i != 0):
                print(i,np.mean(result[0],axis=0))
                #print(self.gelman_rubin_convergence_statistic(self.sampler.chain))
                self.gr_convergence[0].append(i)
                self.gr_convergence[1].append(self.gelman_rubin_convergence_statistic(self.sampler.chain[:,:i,:]))

        return


    def get_initial_walkers(self):
        """Setup initial states of walkers in sensible points"""

        if not self.sampler: raise ValueError('sampler not properly setup')

        ndim=self.ndim
        nwalkers=self.nwalkers

        if self.verbose: 
            print('set %d walkers with %d dimensions'%(nwalkers,ndim))

        if self.like.prior_Gauss_rms is None:
            p0=np.random.rand(ndim*nwalkers).reshape((nwalkers,ndim))
        else:
            rms=self.like.prior_Gauss_rms
            p0=np.ndarray([nwalkers,ndim])
            for i in range(ndim):
                p=self.like.free_params[i]
                fid_value=p.value_in_cube()
                values=self.get_trunc_norm(fid_value,nwalkers)
                assert np.all(values >= 0.0)
                assert np.all(values <= 1.0)
                p0[:,i]=values

        return p0


    def get_trunc_norm(self,mean,n_samples):
        """ Wrapper for scipys truncated normal distribution
        Runs in the range [0,1] with a rms specified on initialisation """

        rms=self.like.prior_Gauss_rms
        values=scipy.stats.truncnorm.rvs((0.0-mean)/rms,
                            (1.0-mean)/rms, scale=rms,
                            loc=mean, size=n_samples)

        return values


    def log_prob(self,values):
        """Function that will actually be called by emcee"""

        test_log_prob=self.like.log_prob(values=values)
        if np.isnan(test_log_prob):
            if self.verbose:
                print('parameter values outside hull',values)
                return -np.inf
        if self.store_distances:
            self.add_euclidean_distances(values)

        return test_log_prob


    def add_euclidean_distances(self,values):
        """ For a given set of likelihood parameters
        find the Euclidean distances to the nearest
        training point for each emulator call """

        emu_calls=self.like.theory.get_emulator_calls(self.like.parameters_from_sampling_point(values))
        for aa,call in enumerate(emu_calls):
            self.distances[aa].append(self.like.theory.emulator.get_nearest_distance(call,z=self.like.data.z[aa]))

        return 


    def go_silent(self):
        self.verbose=False
        self.like.go_silent()


    def get_chain(self):
        """Figure out whether chain has been read from file, or computed"""

        if not self.chain_from_file is None:
            chain=self.chain_from_file['chain']
            lnprob=self.chain_from_file['lnprob']
        else:
            if not self.sampler: raise ValueError('sampler not properly setup')
            chain=self.sampler.flatchain
            lnprob=self.sampler.flatlnprobability

        return chain,lnprob
        

    def gelman_rubin_convergence_statistic(self, chains): 
        """ Gelman rubin convergence.
        Chain dimensions are walkers, steps, parameters """

        n_walkers = chains.shape[0]
        n_steps = chains.shape[1]

        within_chain_variance = np.mean(np.var(chains, axis = 1, ddof = 1), axis = 0) #dimensions: Parameters

        chain_means = np.mean(chains, axis = 1)
        between_chain_variance = np.var(chain_means, axis = 0, ddof = 1) * n_steps

        posterior_marginal_variance = ((n_steps - 1) * within_chain_variance / n_steps) + ((n_walkers + 1) * between_chain_variance / n_steps / n_walkers)

        return np.sqrt(posterior_marginal_variance / within_chain_variance)


    def plot_gelman_rubin_convergence(self):
        """ Plot the PSRF for each parameter as a function of
        iteration number """

        plt.figure()
        for aa,par in enumerate(self.like.free_parameters):
            ## Create a list of the PSRF for each param
            psrf=[]
            for bb in range(len(self.gr_convergence[0])):
                psrf.append(self.gr_convergence[1][bb][aa])
            plt.plot(self.gr_convergence[0],psrf,label=par)

        plt.title("%d walkers" % self.nwalkers)
        plt.xlabel("Number of steps")
        plt.ylabel("PSRF")
        plt.legend()
        if self.save_directory:
            plt.savefig(self.save_directory+"/psrf.pdf")
        else:
            plt.show()

        return


    def read_chain_from_file(self,chain_number):
        """Read chain from file, and check parameters"""

        repo=os.environ['LYA_EMU_REPO']
        self.save_directory=repo+"/lya_sampler/chains/chain_"+str(chain_number)

        with open(self.save_directory+"/config.json") as json_file:  
            config = json.load(json_file)

        ## Set up the arxiv
        archive=p1d_arxiv.ArxivP1D(basedir=config["basedir"],
                            drop_tau_rescalings=config["drop_tau_rescalings"],
                            drop_temp_rescalings=config["drop_temp_rescalings"],
                            z_max=config["z_max"],
                            drop_sim_number=config["data_sim_number"],
                            p1d_label=config["p1d_label"],                            
                            skewers_label=config["skewers_label"],
                            undersample_cube=config["undersample_cube"])


        ## Set up the emulators
        if config["z_emulator"]:
            emulator=z_emulator.ZEmulator(paramList=config["paramList"],
                                train=False,
                                emu_type=config["emu_type"],
                                kmax_Mpc=config["kmax_Mpc"],
                                passArxiv=archive)
            ## Now loop over emulators, passing the saved hyperparameters
            for aa,emu in enumerate(emulator.emulators):
                ## Load emulator hyperparams..
                emu.load_hyperparams(np.asarray(config["emu_hyperparameters"][aa]))
        else:
            emulator=gp_emulator.GPEmulator(paramList=config["paramList"],
                                train=False,
                                emu_type=config["emu_type"],
                                kmax_Mpc=config["kmax_Mpc"],
                                passArxiv=archive)
            emulator.load_hyperparams(np.asarray(config["emu_hyperparameters"]))

        ## Set up mock data
        data=data_MPGADGET.P1D_MPGADGET(sim_number=config["data_sim_number"],
                                    z_list=np.asarray(config["z_list"]))

        ## Set up likelihood
        free_param_list=[]
        limits_list=[]
        for item in config["free_params"]:
            free_param_list.append(item[0])
            limits_list.append([item[1],item[2]])
        if config["simpleLike"]==True:
            self.like=likelihood.simpleLikelihood(data=data,emulator=emulator,
                            free_parameters=free_param_list,
                            verbose=False,
                            prior_Gauss_rms=config["prior_Gauss_rms"])
        else:
            self.like=likelihood.Likelihood(data=data,emulator=emulator,
                            free_parameters=free_param_list,
                            verbose=False,
                            prior_Gauss_rms=config["prior_Gauss_rms"])

        ## Load chains
        self.chain_from_file={}
        self.chain_from_file["chain"]=np.asarray(config["flatchain"])
        self.chain_from_file["lnprob"]=np.asarray(config["lnprob"])


        print("Chain shape is ", np.shape(self.chain_from_file["chain"]))

        self.ndim=len(self.like.free_params)

        return


    def _setup_chain_folder(self):
        """ Set up a directory to save files for this
        sampler run """

        repo=os.environ['LYA_EMU_REPO']
        base_string=repo+"/lya_sampler/chains/chain_"
        chain_count=1
        sampler_directory=base_string+str(chain_count)
        while os.path.isdir(sampler_directory):
            chain_count+=1
            sampler_directory=base_string+str(chain_count)

        os.mkdir(sampler_directory)
        if self.verbose:
            print("Made directory: ", sampler_directory)
        self.save_directory=sampler_directory

        return 


    def _write_dict_to_text(self,saveDict):
        """ Write the settings for this chain
        to a more easily readable .txt file """
        
        ## What keys don't we want to include in the info file
        dontPrint=["lnprob","flatchain"]

        with open(self.save_directory+'/info.txt', 'w') as f:
            for item in saveDict.keys():
                if item not in dontPrint:
                    f.write("%s: %s\n" % (item,str(saveDict[item])))

        return


    def write_chain_to_file(self):
        """Write flat chain to file"""
        
        self._setup_chain_folder()

        saveDict={}
        ## Arxiv settings
        saveDict["basedir"]=self.like.theory.emulator.arxiv.basedir
        saveDict["skewers_label"]=self.like.theory.emulator.arxiv.skewers_label
        saveDict["p1d_label"]=self.like.theory.emulator.arxiv.p1d_label
        saveDict["drop_tau_rescalings"]=self.like.theory.emulator.arxiv.drop_tau_rescalings
        saveDict["drop_temp_rescalings"]=self.like.theory.emulator.arxiv.drop_temp_rescalings
        saveDict["nearest_tau"]=self.like.theory.emulator.arxiv.nearest_tau
        saveDict["z_max"]=self.like.theory.emulator.arxiv.z_max
        saveDict["undersample_cube"]=self.like.theory.emulator.arxiv.undersample_cube

        ## Emulator settings
        saveDict["paramList"]=self.like.theory.emulator.paramList
        saveDict["kmax_Mpc"]=self.like.theory.emulator.kmax_Mpc
        if self.like.theory.emulator.emulators is not None:
            z_emulator=True
            emu_hyperparams=[]
            for emu in self.like.theory.emulator.emulators:
                emu_hyperparams.append(emu.gp.param_array.tolist())
        else:
            z_emulator=False
            emu_hyperparams=self.like.theory.emulator.gp.param_array.tolist()
        saveDict["z_emulator"]=z_emulator
        saveDict["emu_hyperparameters"]=emu_hyperparams
        saveDict["emu_type"]=self.like.theory.emulator.emu_type

        ## Likelihood & data settings
        saveDict["prior_Gauss_rms"]=self.like.prior_Gauss_rms
        saveDict["z_list"]=self.like.theory.zs.tolist()
        saveDict["ignore_emu_cov"]=self.like.ignore_emu_cov
        saveDict["data_basedir"]=self.like.data.basedir
        saveDict["data_sim_number"]=self.like.data.sim_number
        if self.like.simpleLike:
            saveDict["simpleLike"]=True
        else:
            saveDict["simpleLike"]=False
        free_params_save=[]
        for par in self.like.free_params:
            free_params_save.append([par.name,par.min_value,par.max_value])
        saveDict["free_params"]=free_params_save

        ## Sampler stuff
        saveDict["burn_in"]=self.burnin_nsteps
        saveDict["nwalkers"]=self.nwalkers
        saveDict["lnprob"]=self.sampler.flatlnprobability.tolist()
        saveDict["flatchain"]=self.sampler.flatchain.tolist()

        ## Save dictionary to json file in the
        ## appropriate directory
        with open(self.save_directory+"/config.json", "w") as json_file:
            json.dump(saveDict,json_file)

        self._write_dict_to_text(saveDict)

        ## Save plots
        self.plot_best_fit()
        self.plot_prediction()
        self.plot_corner()
        self.plot_gelman_rubin_convergence()

        return


    def plot_histograms(self,cube=False):
        """Make histograms for all dimensions, using re-normalized values if
            cube=True"""

        # get chain (from sampler or from file)
        chain,lnprob=self.get_chain()

        for ip in range(self.ndim):
            param=self.like.free_params[ip]
            if cube:
                values=chain[:,ip]
                title=param.name+' in cube'
            else:
                cube_values=chain[:,ip]
                values=param.value_from_cube(cube_values)
                title=param.name

            plt.hist(values, 100, color="k", histtype="step")
            plt.title(title)
            plt.show()

        return


    def plot_corner(self,cube=False,mock_values=True):
        """Make corner plot, using re-normalized values if cube=True"""

        # get chain (from sampler or from file)
        chain,lnprob=self.get_chain()

        labels=[]
        for p in self.like.free_params:
            if cube:
                labels.append(p.name+' in cube')
            else:
                labels.append(p.name)

        if cube:
            values=chain
        else:
            cube_values=chain
            list_values=[self.like.free_params[ip].value_from_cube(
                                cube_values[:,ip]) for ip in range(self.ndim)]
            values=np.array(list_values).transpose()

        figure = corner.corner(values,labels=labels,
                                hist_kwargs={"density":True,"color":"blue"})

        # Extract the axes
        axes = np.array(figure.axes).reshape((self.ndim, self.ndim))
        if mock_values==True:
            if cube:
                list_mock_values=[self.like.free_params[aa].value_in_cube() for aa in range(
                                                len(self.like.free_params))]
            else:
                list_mock_values=[self.like.free_params[aa].value for aa in range(
                                                len(self.like.free_params))]

            # Loop over the diagonal
            for i in range(self.ndim):
                ax = axes[i, i]
                ax.axvline(list_mock_values[i], color="r")
                prior=self.get_trunc_norm(self.like.free_params[i].value_in_cube(),
                                                    100000)
                if cube:
                    ax.hist(prior,bins=200,alpha=0.4,color="hotpink",density=True)
                else:
                    for aa in range(len(prior)):
                        prior[aa]=self.like.free_params[i].value_from_cube(prior[aa])
                    ax.hist(prior,bins=50,alpha=0.4,color="hotpink",density=True)

            # Loop over the histograms
            for yi in range(self.ndim):
                for xi in range(yi):
                    ax = axes[yi, xi]
                    ax.axvline(list_mock_values[xi], color="r")
                    ax.axhline(list_mock_values[yi], color="r")
                    ax.plot(list_mock_values[xi], list_mock_values[yi], "sr")

        if self.save_directory:
            plt.savefig(self.save_directory+"/corner.pdf")
        else:
            plt.show()
        return


    def plot_best_fit(self):

        """ Plot the P1D of the data and the emulator prediction
        for the MCMC best fit
        """

        ## Get best fit values for each parameter
        chain,lnprob=self.get_chain()
        mean_value=[]
        for parameter_distribution in np.swapaxes(chain,0,1):
            mean_value.append(np.mean(parameter_distribution))
        print("Mean values:", mean_value)
        self.like.plot_p1d(values=mean_value)
        plt.title("MCMC best fit")
        if self.save_directory:
            plt.savefig(self.save_directory+"/best_fit.pdf")
        else:
            plt.show()

        return

    def plot_prediction(self):

        """ Plot the P1D of the data and the emulator prediction
        for the fiducial model """

        plt.figure()
        self.like.plot_p1d(values=None)
        plt.title("Fiducial model")
        if self.save_directory:
            plt.savefig(self.save_directory+"/fiducial.pdf")
        else:
            plt.show()

        return


