import os
import sys
import json
import configargparse
from shutil import copy
# figure out path to MP-Gadget
if 'MP_GADGET_DIR' in os.environ:
    mp_gadget_dir=os.environ['MP_GADGET_DIR']
else:
    mp_gadget_dir='/home/dc-pede1/Codes/MP-Gadget-Stable/'
print('mp gadget dir',mp_gadget_dir)
sys.path.append(mp_gadget_dir+'/tools/')
import make_class_power
import write_submit_simulation_dirac as wsd

# get options from command line
parser = configargparse.ArgumentParser()
parser.add_argument('-c', '--config', required=False, is_config_file=True, help='config file path')
parser.add_argument('--basedir', type=str, help='Base directory where all sims will be stored (crashes if it does not exist)',required=True)
parser.add_argument('--nodes', type=int, default=2, help='Number of nodes to use to run GenIC and MP-Gadget')
parser.add_argument('--time', type=str, default='01:00:00', help='String formatted time to pass to SLURM script')
parser.add_argument('--run', action='store_true', help='Actually submit the SLURM scripts (for now, only possible if total nodes < 100)')
parser.add_argument('--verbose', action='store_true', help='Print runtime information',required=False)

args = parser.parse_args()

print('--- print options from parser ---')
print(args)
print("----------")
print(parser.format_help())
print("----------")
print(parser.format_values())
print("----------")

verbose=args.verbose
basedir=args.basedir
nodes=args.nodes
time=args.time

# read information about the hypercube
cube_json=basedir+'/latin_hypercube.json'
with open(cube_json) as json_data:
    cube_data = json.load(json_data)
if verbose:
    print('print cube info')
    print(cube_data)

# get number of samples in the hyper-cube
nsamples=cube_data['nsamples']

# directory to LyaCosmoParams repo
if 'LYA_EMU_REPO' in os.environ:
    lya_emu_repo=os.environ['LYA_EMU_REPO']
else:
    lya_emu_repo='/home/dc-font1/Codes/LyaCosmoParams/'

# get TREECOOL file 
treecool_file=lya_emu_repo+'/setup_simulations/test_sim/TREECOOL_P18.txt'

# for each sample, run make_class_power and copy the files to the right path
for sample in range(nsamples):
    # full path to folder for this particular simulation pair
    pair_dir=basedir+'/sim_pair_'+str(sample)
    if verbose:
        print('writing scripts for pair in',pair_dir)

    # full path to one each simulation in the pair
    plus_dir=pair_dir+'/sim_plus/'
    minus_dir=pair_dir+'/sim_minus/'

    # copy treecool file to both folders
    copy(treecool_file, plus_dir)
    copy(treecool_file, minus_dir)

    # write submission script to both simulations
    plus_submit=plus_dir+'/simulation.sub'
    wsd.write_simulation_script(script_name=plus_submit,simdir=plus_dir,
                          nodes=nodes,time=time,mp_gadget_dir=mp_gadget_dir)
    minus_submit=minus_dir+'/simulation.sub'
    wsd.write_simulation_script(script_name=minus_submit,simdir=minus_dir,
                          nodes=nodes,time=time,mp_gadget_dir=mp_gadget_dir)

    # run make_class_power to generate matterpow.dat and transfer.dat
    try:
        failed=False
        make_class_power.make_class_power(paramfile=plus_dir+'/paramfile.genic')
        # copy to the other simulation in the pair
        copy(plus_dir+'/matterpow.dat', minus_dir)
        copy(plus_dir+'/transfer.dat', minus_dir)
    except:
        failed=True
        print('you will have to run make_class manually for',sample)

    if args.run:
        if failed:
            print('will NOT submit scripts, we need to run make_class')
            continue
        total_nodes=2*args.nodes*nsamples
        if total_nodes < 100:
            print('will submit scripts, for a total of {} nodes'.format(total_nodes))
            cmd_plus='sbatch '+plus_submit+' > '+plus_dir+'/info_sim_sub'
            os.system(cmd_plus)
            cmd_minus='sbatch '+minus_submit+' > '+minus_dir+'/info_sim_sub'
            os.system(cmd_minus)
        else:
            print('will NOT submit scripts, too many nodes = {}'.format(total_nodes))

