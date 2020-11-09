import sys
import filecmp
from pathlib import Path
from shutil import copyfile, rmtree

from librec_auto.core.cmd.rerank_cmd import RerankCmd
from librec_auto.core import ConfigCmd

RERANK_DIR = 'librec_auto/test/core/cmd/rerank'

RERANK_DATA_DIR = 'librec_auto/test/data/rerank'


def test_run_script():
    # set command line target flag
    sys.argv = ['-t', RERANK_DIR]

    # create file structure

    # mkdir rerank
    rerank_path = Path(RERANK_DIR)
    rerank_path.mkdir(exist_ok=True)

    # make study conf directory
    study_conf_path = (rerank_path / Path('conf'))
    study_conf_path.mkdir(exist_ok=True)

    # copy study config
    copyfile(RERANK_DATA_DIR / Path('rerank-study-config.xml'),
             study_conf_path / 'config.xml')

    # make experiment directory
    experiment_path = (rerank_path / Path('exp00000'))
    experiment_path.mkdir(exist_ok=True)

    # make original directory
    original_path = (experiment_path / Path('original'))
    original_path.mkdir(exist_ok=True)

    # copy out-1.txt and out-2.txt to original directory
    copyfile(RERANK_DATA_DIR / Path('original-out-1.txt'),
             original_path / 'out-1.txt')
    copyfile(RERANK_DATA_DIR / Path('original-out-2.txt'),
             original_path / 'out-2.txt')

    # make experiment conf directory
    experiment_conf_path = (experiment_path / Path('conf'))
    experiment_conf_path.mkdir(exist_ok=True)

    # copy experiment config
    copyfile(RERANK_DATA_DIR / Path('rerank-experiment-config.xml'),
             experiment_conf_path / 'config.xml')

    # make results directory
    results_path = (experiment_path / Path('result'))
    results_path.mkdir(exist_ok=True)

    # create config
    config = ConfigCmd(RERANK_DIR + '/conf/config.xml', RERANK_DIR)

    # initialize rerankCmd
    rerank = RerankCmd()

    script = Path('../../../../../librec_auto/core/cmd/rerank/far_rerank.py')

    param_spec = ['--max_len=4', '--lambda=0.3', '--binary=False']

    rerank._files = config.get_files()

    rerank._files.create_exp_paths(0)  # create experiment tuple

    sub_paths = rerank._files.get_exp_paths(0)

    rerank._config = config  # set config

    result = rerank.run_script(script=script,
                               sub_paths=sub_paths,
                               original_path=original_path,
                               param_spec=param_spec)

    assert result == 0  # check that the script ran successfully

    # check the reranked results are correct
    assert filecmp.cmp(RERANK_DATA_DIR / Path('result-out-1.txt'),
                       results_path / 'out-1.txt')
    assert filecmp.cmp(RERANK_DATA_DIR / Path('result-out-2.txt'),
                       results_path / 'out-2.txt')

    rmtree(RERANK_DIR)  # delete the reranking directory
