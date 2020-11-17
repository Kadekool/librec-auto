import argparse
from pathlib import Path
from librec_auto.core import read_config_file
from librec_auto.core.util import Files
from librec_auto.core.cmd import Cmd, SetupCmd, SequenceCmd, PurgeCmd, LibrecCmd, PostCmd, RerankCmd, StatusCmd, ParallelCmd
import logging
import librec_auto


def read_args():
    '''
    Parse command line arguments.
    :return:
    '''
    parser = argparse.ArgumentParser(
        description='The librec-auto tool for running recommender systems experiments.',
        epilog='TODO- This is a work in progress. For now, refer to this link: https://librec-auto.readthedocs.io/en/latest/'
    )
    parser.add_argument('action',
                        choices=[
                            'run', 'split', 'eval', 'rerank', 'post', 'purge',
                            'status', 'describe', 'check'
                        ])

    parser.add_argument("-t", "--target", help="Path to experiment directory")

    # Optional with arguments
    # parser.add_argument("-ex","--exhome", help="stub")
    # parser.add_argument("-rs","--reset", help = "stub")
    # parser.add_argument("-rss","--revise-step", help="stub")
    parser.add_argument("-c",
                        "--conf",
                        help="Use the specified configuration file")

    # Flags
    parser.add_argument(
        "-dr",
        "--dry_run",
        help="Show sequence of command execution but do not execute commands",
        action="store_true")
    parser.add_argument("-q",
                        "--quiet",
                        help="Skip confirmation when purging",
                        action="store_true")
    parser.add_argument(
        "-np",
        "--no_parallel",
        help="Ignore thread-count directive and run all operations sequentially",
        action="store_true")
    parser.add_argument(
        "-p",
        "--purge",
        help="Purge results of step given in <option> and all subsequent steps",
        choices=['all', 'split', 'results', 'rerank', 'post'],
        default='all')
    parser.add_argument(
        "-nc",
        "--no_cache",
        help="Do not cache any intermediate results (Not implemented)",
        action="store_true")
    parser.add_argument(
        "-dev",
        "--dev",
        help="Help with documentation, code formatting, and Docker",
        action="store_true")
    parser.add_argument("-HT",
                        "--HT",
                        help="Help with using libraries (Not implemented)",
                        action="store_true")
    parser.add_argument(
        "-PCO",
        "--PCO",
        help="Help with producting CSV outputs (Not implemented)",
        action="store_true")
    parser.add_argument("-int",
                        "--int",
                        help="Help with Integrations (Not implemented)",
                        action="store_true")

    parser.add_argument(
        "-k",
        "--key_password",
        help="Password for the API keys used by post-processing scripts")

    input_args = parser.parse_args()
    return vars(input_args)


def load_config(args):

    config_file = Files.DEFAULT_CONFIG_FILENAME

    if args['conf']:  # User requested a different configuration file
        config_file = args['conf']

    target = ""
    if (args['target'] != None):
        target = args['target']

    return read_config_file(config_file, target)


DESCRIBE_TEXT = 'Librec-auto automates recommender systems experimentation using the LibRec Java library.\n' +\
    '\tA librec-auto experiment consist of five steps governed by the specifications in the configuration file:\n' +\
    '\t- split: Create training / test splits from a data set. (LibRec)\n' +\
    '\t- exp: Run an experiment generating recommendations for a test set (LibRec)\n' +\
    '\t- rerank (optional): Re-rank the results of the experiment (script)\n' +\
    '\t- eval: Evaluate the results of a recommendation experiment (LibRec)\n' +\
    '\t- post (optional): Perform post-processing computations (script)\n' + \
    'Steps labeled LibRec are performed by the LibRec library using configuration properties generated by librec-auto.\n' +\
    'Steps labeled script are performed by experimenter-defined scripts.\n' + \
    'Run librec_auto describe <step> for additional information about each option.'

DESCRIBE_DICT = {
    'run':
    'Run a complete librec-auto experiment. Re-uses cached results if any. \
May result in no action if all computations are up-to-date and no purge option is specified.',
    'split': 'Run the training / test split only',
    'exp': 'Run the experiment, re-ranking, evaluation, and post-processing',
    'rerank': 'Run the re-ranking, evaluation and post-processing',
    'eval': 'Run the evaluation and post-processing',
    'post': 'Run post-processing steps',
    'purge':
    'Purge cached computations. Uses -p flag to determine what to purge',
    'status': 'Print out the status of the experiments'
}


def print_description(args):
    act = args['target']
    if act in DESCRIBE_DICT:
        print(f'core {act} <target>: {DESCRIBE_DICT[act]}')
    else:
        print(DESCRIBE_TEXT)


def purge_type(args):
    if 'purge' in args:
        return args['purge']
    # If no type specified and you're purging, purge everything
    elif args['action'] == 'purge':
        return 'split'
    else:
        return 'none'


# TODO: Need to rewrite as "build_exec_commands" where the action incorporates both execution
# and reranking. Remember that the re-ranker only requires one run of the prediction algorithm for any
# variation its own parameters.
def build_librec_commands(librec_action, args, config):
    librec_commands = [
        LibrecCmd(librec_action, i) for i in range(config.get_sub_exp_count())
    ]
    threads = config.thread_count()

    if threads > 1 and not args['no_parallel']:
        return ParallelCmd(librec_commands, threads)
    else:
        return SequenceCmd(librec_commands)


# The purge rule is: if the command says to run step X, purge the results of X and everything after.
def setup_commands(args, config):
    action = args['action']
    purge_noask = args['quiet']

    # Create flags for optional steps
    rerank_flag = config.has_rerank()
    post_flag = config.has_post()

    # Set the password in the configuration if we have it
    if args['key_password']:
        config.set_key_password(args['key_password'])

    # Purge files (possibly) from splits and subexperiments
    if action == 'purge':
        cmd = PurgeCmd(purge_type(args), noask=purge_noask)
        return cmd

    # Shows the status of the experiment
    if action == 'status':
        cmd = StatusCmd()
        return cmd

    # Perform (only) post-processing on results
    if action == 'post' and post_flag:
        cmd = PostCmd()
        return cmd
    # No post scripts available
    if action == 'post' and not post_flag:
        logging.warning(
            "No post-processing scripts available for post command.")
        return None

    # Perform re-ranking on results, followed by evaluation and post-processing
    if action == 'rerank' and rerank_flag:  # Runs a reranking script on the python side
        cmd1 = PurgeCmd('rerank', noask=purge_noask)
        cmd2 = SetupCmd()
        cmd3 = RerankCmd()
        cmd4 = build_librec_commands('eval', args, config)
        cmd = SequenceCmd([cmd1, cmd2, cmd3, cmd4])
        if post_flag:
            cmd.add_command(PostCmd())
        return cmd
    # No re-ranker available
    if action == 'rerank' and not rerank_flag:
        logging.warning("No re-ranker available for rerank command.")
        return None

    # LibRec actions
    # re-run splits only
    if action == 'split':
        cmd1 = PurgeCmd('split', noask=purge_noask)
        cmd2 = SetupCmd()
        cmd3 = build_librec_commands('split', args, config)
        cmd = SequenceCmd([cmd1, cmd2, cmd3])
        return cmd

    # re-run experiment and continue
    if action == 'run':
        cmd1 = PurgeCmd('results', noask=purge_noask)
        cmd2 = SetupCmd()
        cmd3 = build_librec_commands('full', args, config)
        cmd = SequenceCmd([cmd1, cmd2, cmd3])
        if rerank_flag:
            cmd.add_command(RerankCmd())
            cmd.add_command(build_librec_commands('eval', args, config))
        if post_flag:
            cmd.add_command(PostCmd())
        return cmd

    # eval-only
    if action == 'eval':
        cmd1 = PurgeCmd('post', noask=purge_noask)
        cmd2 = SetupCmd()
        cmd3 = build_librec_commands('eval', args, config)
        cmd = SequenceCmd([cmd1, cmd2, cmd3])
        if post_flag:
            cmd.add_command(PostCmd())
        return cmd

    if action == 'check':
        cmd = build_librec_commands('check', args, config)
        return cmd


# -------------------------------------

if __name__ == '__main__':
    args = read_args()

    jar_path = Path(librec_auto.__file__).parent / "jar" / "auto.jar"
    if not jar_path.is_file():
        print(
            "Error: LibRec JAR file is missing."
        )

    else:
        if args['action'] == 'describe':
            print_description(args)
        else:
            config = load_config(args)

            if config.is_valid():
                command = setup_commands(args, config)
                if isinstance(command, Cmd):
                    if args['dry_run']:
                        command.dry_run(config)
                    else:
                        command.execute(config)
                else:
                    logging.error("Command instantiation failed.")
            else:
                logging.error("Configuration loading failed.")
