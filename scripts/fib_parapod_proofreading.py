import os
from z5py.util import copy_group


def make_initial_dataset(out_path):
    path = '/g/kreshuk/data/schwab/parapodia_rachel/data.n5'
    in_key = 'volumes/paintera/lmc_nuclei_v1_fragments'
    out_key = 'volumes/segmentation'
    # copy the paintera dataset
    # FIXME this memory errs
    print("Start copying...")
    copy_group(path, out_path, in_key, out_key, 8)
    # make link to raw data
    os.symlink(os.path.join(path, 'volumes/raw'),
               os.path.join(out_path, 'volumes/raw'))


if __name__ == '__main__':
    make_initial_dataset('/g/kreshuk/pape/Work/my_projects/paintera_projects/proofreading_fib_parapod/v1_rachel.n5')