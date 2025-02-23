import os
import json
import luigi
from cluster_tools.paintera import ConversionWorkflow

from ..util import write_global_config


def convert_to_paintera_format(path, raw_key, in_key, out_key,
                               label_scale, resolution,
                               tmp_folder, target, max_jobs, max_threads,
                               assignment_path='', assignment_key=''):

    config_folder = os.path.join(tmp_folder, 'configs')
    write_global_config(config_folder)

    configs = ConversionWorkflow.get_config()
    config = configs['downscaling']
    config.update({"library_kwargs": {"order": 0}, "mem_limit": 12, "time_limit": 120})
    with open(os.path.join(config_folder, "downscaling.config"), 'w') as f:
        json.dump(config, f)

    block_mapping_conf = configs['label_block_mapping']
    block_mapping_conf.update({'mem_limit': 100, 'time_limit': 360, 'threads_per_job': max_threads})
    with open(os.path.join(config_folder, 'label_block_mapping.config'), 'w') as f:
        json.dump(block_mapping_conf, f)

    task = ConversionWorkflow(tmp_folder=tmp_folder, config_dir=config_folder,
                              max_jobs=max_jobs, target=target,
                              path=path, raw_key=raw_key,
                              label_in_key=in_key,
                              label_out_key=out_key,
                              assignment_path=assignment_path, assignment_key=assignment_key,
                              label_scale=label_scale, resolution=resolution)
    ret = luigi.build([task], local_scheduler=True)
    assert ret, "Conversion to paintera format failed"
