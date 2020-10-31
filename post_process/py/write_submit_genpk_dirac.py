import numpy as np
import os
import read_gadget
import flux_real_genpk

def get_submit_string(options,time,output_files):
    submit_string='''#!/bin/bash -l
#! sbatch directives begin here ###############################
#! Name of the job:
#SBATCH -J genpk_fluxreal
#SBATCH --nodes=1
#SBATCH --ntasks=40
#SBATCH --time='20:00:00' 
#SBATCH -o %s.out
#SBATCH -e %s.err
#SBATCH --time=%s
#SBATCH --mail-type=NONE
#SBATCH -p RCIF

#! Number of nodes and tasks per node allocated by SLURM (do not change):
numnodes=$SLURM_JOB_NUM_NODES
numtasks=$SLURM_NTASKS
mpi_tasks_per_node=$(echo "$SLURM_TASKS_PER_NODE" | sed -e  's/^\([0-9][0-9]*\).*$/\1/')

## Load modules
module load python/3.6.4
module load hdf5/1.10.1

#! Full path to application executable: 
lya_scripts="/home/chrisp/Projects/LyaCosmoParams/post_process/scripts"
application="python3 $lya_scripts/run_genpk_flux_real.py"

# setup options 
options="%s"

workdir="$SLURM_SUBMIT_DIR"  # The value of SLURM_SUBMIT_DIR sets workdir to the directory
JOBID=$SLURM_JOB_ID
                             # in which sbatch is run.
export OMP_NUM_THREADS=1
np=$[${numnodes}*${mpi_tasks_per_node}]
export I_MPI_PIN_DOMAIN=omp:compact # Domains are $OMP_NUM_THREADS cores in size
export I_MPI_PIN_ORDER=scatter # Adjacent domains have minimal sharing of caches/sockets
CMD="$application $options"
cd $workdir
echo -e "Changed directory to `pwd`.
"
echo -e "JobID: $JOBID
======"
echo "Time: `date`"
echo "Running on master node: `hostname`"
echo "Current directory: `pwd`"
if [ "$SLURM_JOB_NODELIST" ]; then
        #! Create a machine file:
        export NODEFILE=`generate_pbs_nodefile`
        cat $NODEFILE | uniq > machine.file.$JOBID
        echo -e "
Nodes allocated:
================"
        echo `cat machine.file.$JOBID | sed -e 's/\..*$//g'`
fi
echo -e "
numtasks=$numtasks, numnodes=$numnodes, mpi_tasks_per_node=$mpi_tasks_per_node (OMP_NUM_THREADS=$OMP_NUM_THREADS)"
echo -e "
Executing command:
==================
$CMD
"
eval $CMD
'''%(output_files,output_files,time,options)
    return submit_string
    

def get_options_string(simdir,snap_num,verbose):
    """ Option string to pass to python script in SLURM"""

    options='--simdir {} --snap_num {} '.format(simdir,snap_num)
    if verbose:
        options+='--verbose'

    return options


def write_genpk_script(script_name,simdir,snap_num,time,verbose):
    """ Generate a SLURM file to run GenPk for a given snapshot."""

    # construct string with options to be passed to python script
    options=get_options_string(simdir,snap_num,verbose)

    if verbose:
        print('print options: '+options)

    # set output files (.out and .err)
    output_files=simdir+'/slurm_genpk_'+str(snap_num)

    # get string with submission script
    submit_string=get_submit_string(options,time,output_files)

    submit_script = open(script_name,'w')
    for line in submit_string:
        submit_script.write(line)
    submit_script.close()


def write_genpk_scripts_in_sim(simdir,time,verbose):
    """ Generate a SLURM file for each snapshot to run GenPk"""
    
    if verbose:
        print('in write_genpk_scripts_in_sim',simdir)

    # get redshifts / snapshots Gadget parameter file 
    paramfile=simdir+'/paramfile.gadget'
    zs=read_gadget.redshifts_from_paramfile(paramfile)
    Nsnap=len(zs)

    for snap in range(Nsnap):
        # figure out if GenPk was already computed
        genpk_filename=flux_real_genpk.flux_real_genpk_filename(simdir,snap)
        print('genpk filename =',genpk_filename)
        if os.path.exists(genpk_filename):
            if verbose: print('GenPk file existing',genpk_filename)
            continue
        else:
            if verbose: print('Will generate genpk file',genpk_filename)

        slurm_script=simdir+'/genpk_%s.sub'%snap
        write_genpk_script(script_name=slurm_script,simdir=simdir,
                            snap_num=snap,time=time,verbose=verbose)
        info_file=simdir+'/info_sub_genpk_'+str(snap)
        if verbose:
            print('print submit info to',info_file)
        cmd='sbatch '+slurm_script+' > '+info_file
        os.system(cmd)

