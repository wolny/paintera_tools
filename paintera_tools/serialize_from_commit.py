import os
import json
import numpy as np

import luigi
import vigra
import z5py
from cluster_tools.write import WriteLocal, WriteSlurm
from cluster_tools.relabel import UniqueWorkflow

from .util import save_assignments


def write_global_config(tmp_folder, path, key):
    config_folder = os.path.join(tmp_folder, 'configs')
    os.makedirs(config_folder, exist_ok=True)
    global_config = WriteLocal.default_global_config()

    with z5py.File(path) as f:
        block_shape = f[key].chunks

    # TODO allow specifying the shebang
    shebang = '#! /g/kreshuk/pape/Work/software/conda/miniconda3/envs/cluster_env37/bin/python'
    global_config['shebang'] = shebang
    global_config.update({'shebang': shebang, 'block_shape': block_shape})
    with open(os.path.join(config_folder, 'global.config'), 'w') as f:
        json.dump(global_config, f)


def find_uniques(path, seg_in_key, out_path, out_key,
                 tmp_folder, max_jobs, target):
    task = UniqueWorkflow
    config_folder = os.path.join(tmp_folder, 'configs')

    t = task(tmp_folder=tmp_folder, config_dir=config_folder,
             max_jobs=max_jobs, target=target,
             input_path=path, input_key=seg_in_key,
             output_path=out_path, output_key=out_key)
    ret = luigi.build([t], local_scheduler=True)
    if not ret:
        raise RuntimeError("Writing merged segmentation failed")


def make_dense_assignments(fragment_ids, assignments):

    # make dense assignments
    # initially, each fragment id is assigned its own id as segment id
    dense_assignments = np.zeros((len(fragment_ids), 2), dtype='uint64')
    dense_assignments[:, 0] = fragment_ids
    dense_assignments[:, 1] = fragment_ids

    # find all fragments that have a segment id assigned
    with_assignment = np.in1d(fragment_ids, assignments[:, 0])
    assert np.sum(with_assignment) == len(assignments)
    dense_assignments[:, 1][with_assignment] = assignments[:, 1]

    # set the paintera ignore label assignment to 0
    paintera_ignore_label = 18446744073709551615
    if dense_assignments[-1, 0] == paintera_ignore_label:
        dense_assignments[-1, 1] = 0
    return dense_assignments


def serialize_assignments(g, ass_key,
                          save_path, unique_key, save_key,
                          locked_segments=None, relabel_output=False):

    # load the unique ids
    f = z5py.File(save_path)
    fragment_ids = f[unique_key][:]

    # load the assignments
    assignments = g[ass_key][:].T
    dense_assignments = make_dense_assignments(fragment_ids, assignments)

    # only keep assignments corresponding to locked segments
    # if locked segments are given
    if locked_segments is not None:
        locked_mask = np.in1d(dense_assignments[:, 1], locked_segments)
        dense_assignments[:, 1][np.logical_not(locked_mask)] = 0

    # relabel the assignments consecutively
    if relabel_output:
        values = dense_assignments[:, 1]
        vigra.analysis.relabelConsecutive(values, start_label=1, keep_zeros=True,
                                          out=values)
        dense_assignments[:, 1] = values

    save_assignments(dense_assignments, save_path, save_key)


def serialize_merged_segmentation(path, key, out_path, out_key, ass_path, ass_key,
                                  tmp_folder, max_jobs, target):
    task = WriteLocal if target == 'local' else WriteSlurm
    config_folder = os.path.join(tmp_folder, 'configs')
    config = task.default_task_config()

    block_shape = z5py.File(path, 'r')[key].chunks
    config.update({'chunks': block_shape, 'allow_empty_assignments': True})
    with open(os.path.join(config_folder, 'write.config'), 'w') as f:
        json.dump(config, f)

    t = task(tmp_folder=tmp_folder, config_dir=config_folder, max_jobs=max_jobs,
             input_path=path, input_key=key,
             output_path=out_path, output_key=out_key,
             assignment_path=ass_path, assignment_key=ass_key,
             identifier='merge-paintera-seg')
    ret = luigi.build([t], local_scheduler=True)
    if not ret:
        raise RuntimeError("Writing merged segmentation failed")


def serialize_from_commit(path, key, out_path, out_key,
                          tmp_folder, max_jobs, target, scale=0,
                          locked_segments=None, relabel_output=False):
    """ Serialize corrected segmentation from commited project.
    """
    f = z5py.File(path, 'r')
    g = f[key]

    # make sure this is a paintera group
    seg_key = 'data'
    assignment_in_key = 'fragment-segment-assignment'
    assert seg_key in g
    assert assignment_in_key in g

    # prepare cluster tools tasks
    os.makedirs(tmp_folder, exist_ok=True)
    seg_in_key = os.path.join(key, seg_key, 's%i' % scale)
    write_global_config(tmp_folder, path, seg_in_key)

    save_path = os.path.join(tmp_folder, 'assignments.n5')
    unique_key = 'uniques'
    assignment_key = 'assignments'

    # 1.) find the unique ids in the base segemntation
    find_uniques(path, seg_in_key, save_path, unique_key,
                 tmp_folder, max_jobs, target)

    # 2.) make and serialize new assignments
    print("Serializing assignments ...")
    serialize_assignments(g, assignment_in_key,
                          save_path, unique_key, assignment_key,
                          locked_segments, relabel_output)

    # 3.) write the new segmentation
    print("Serializing new segmentation ...")
    serialize_merged_segmentation(path, seg_in_key,
                                  out_path, out_key,
                                  save_path, assignment_key,
                                  tmp_folder, max_jobs, target)