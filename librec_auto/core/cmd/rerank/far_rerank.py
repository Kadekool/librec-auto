# FAR rerank
# Based on W. Liu, R. Burke, Personalizing Fairness-aware Re-ranking

import argparse
import re
import pandas as pd
from librec_auto.core import read_config_file
from pathlib import Path
from librec_auto.core.util.xml_utils import single_xpath


class FarHelper:
    item_feature_df = None
    protected = None
    lam = 0
    max_length = 10
    binary = True
    protected_set = {}

    def is_protected(self, itemid):
        return itemid in self.protected_set

    def num_prot(self, items):
        num_prot = [self.is_protected(itemid) for itemid in items].count(True)
        return num_prot


# Caches the protected items for quicker lookup
def get_protected_set(item_features, helper):
    return set((item_features[(item_features['feature'] == helper.protected)
                              & (item_features['value'] == 1)].index).tolist())


#def is_protected(itemid):
#    item_entry = item_feature_df.loc[itemid]
#    prot_item = item_entry[(item_entry['feature']==protected) & (item_entry['value']==1)]
#    return type(prot_item) == numpy.int64

# def num_prot(items):
#     num_prot = [is_protected(itemid) for itemid in items].count(True)
#     return num_prot


def score_prot(user_profile, helper):
    user_items = user_profile['itemid'].tolist()
    if len(user_items) == 0:
        return 0
    return helper.num_prot(user_items) * 1.0 / len(user_items)


def rescore_binary(item, original_score, items_so_far, score_profile, helper):
    answer = original_score
    div_term = 0

    # If there are both kind of items in the list, no re-ranking happens
    count_prot = helper.num_prot(items_so_far)
    if helper.is_protected(item):
        if count_prot == 0:
            div_term = score_profile
    else:
        if count_prot == len(items_so_far):
            div_term = 1 - score_profile

    div_term *= (1 - helper.lam)
    answer *= helper.lam
    answer += div_term

    return answer


# Not in the original paper, but treats the P(\\bar{s)|d) as real-valued
# See Abdollahpouri, Burke, and Mobasher. Managing popularity bias in recommender systems with personalized re-ranking. 2019
def rescore_prop(item, original_score, items_so_far, score_profile, helper):
    answer = original_score

    count_prot = helper.num_prot(items_so_far)
    count_items = len(items_so_far)
    if count_items == 0:
        div_term = score_profile
    else:
        if helper.is_protected(item):
            div_term = score_profile
            div_term *= 1 - count_prot / count_items
        else:
            div_term = (1 - score_profile)
            div_term *= count_prot / count_items

    div_term *= helper.lam
    answer *= (1 - helper.lam)
    answer += div_term
    return answer


def pick_best(user_recs, user_profile, items_so_far, helper):
    best_item = None
    best_score = -1
    score_profile = score_prot(user_profile, helper)

    for _, _, item, score in user_recs.itertuples():
        if helper.binary:
            new_score = rescore_binary(item, score, items_so_far,
                                       score_profile, helper)
        else:
            new_score = rescore_prop(item, score, items_so_far, score_profile,
                                     helper)
        if new_score > best_score:
            best_item = item
            best_score = new_score

    return (best_item, best_score)


def rerank(userid, user_recs_df, user_profile, helper):
    output_data = []
    items_so_far = []

    for i in range(0, helper.max_length):

        item, score = pick_best(user_recs_df, user_profile, items_so_far,
                                helper)

        items_so_far.append(item)
        output_data.append((userid, item, score))
        new_user_recs = user_recs_df[user_recs_df['itemid'] != item]
        user_recs_df = new_user_recs

    return pd.DataFrame(output_data, columns=['userid', 'itemid', 'score'])


def execute(recoms_df, train_df, helper):

    result = []

    for userid in list(set(recoms_df['userid'])):
        #        print('list reranked for user #',userid)
        result.append(
            rerank(userid, recoms_df[recoms_df['userid'] == userid].copy(),
                   train_df[train_df['userid'] == userid], helper))

    rr_df = pd.concat(result)
    return rr_df


def read_args():
    """
    Parse command line arguments.
    :return:
    """
    parser = argparse.ArgumentParser(description='Generic re-ranking script')
    parser.add_argument('conf', help='Name of configuration file')
    parser.add_argument('original', help='Path to original results directory')
    parser.add_argument('result', help='Path to destination results directory')
    parser.add_argument(
        '--max_len',
        help='The maximum number of items to return in each list',
        default=10)
    parser.add_argument('--lambda', help='The weight for re-ranking.')
    parser.add_argument('--binary',
                        help='Whether P(\\bar{s)|d) is binary or real-valued',
                        default=True)

    input_args = parser.parse_args()
    return vars(input_args)


RESULT_FILE_PATTERN = 'out-(\d+).txt'
INPUT_FILE_PATTERN = 'cv_\d+'


def enumerate_results(result_path):
    pat = re.compile(RESULT_FILE_PATTERN)
    files = [file for file in result_path.iterdir() if pat.match(file.name)]
    files.sort()
    return files


def load_item_features(config, data_path):
    item_feature_file = single_xpath(
        config.get_xml(), '/librec-auto/features/item-feature-file').text
    item_feature_path = data_path / item_feature_file

    if not item_feature_path.exists():
        print("Cannot locate item features. Path: " + item_feature_path)
        return None

    item_feature_df = pd.read_csv(item_feature_path,
                                  names=['itemid', 'feature', 'value'])
    item_feature_df.set_index('itemid', inplace=True)
    return item_feature_df


def load_training(split_path, cv_count):
    tr_file_path = split_path / f'cv_{cv_count}' / 'train.txt'

    if not tr_file_path.exists():
        print('Cannot locate training data: ' + str(tr_file_path.absolute()))
        return None

    tr_df = pd.read_csv(tr_file_path,
                        names=['userid', 'itemid', 'score'],
                        sep='\t')

    return tr_df


def setup_helper(args, config, item_feature_df):
    protected = single_xpath(config.get_xml(),
                             '/librec-auto/metric/protected-feature').text

    helper = FarHelper()
    helper.protected = protected
    helper.protected_set = get_protected_set(item_feature_df, helper)
    helper.lam = float(args['lambda'])
    helper.max_length = int(args['max_len'])
    helper.binary = args['binary'] == 'True'
    return helper


def output_reranked(reranked_df, dest_results_path, file_path):
    output_file_path = dest_results_path / file_path.name
    print('Reranking saved to ', output_file_path)
    reranked_df.to_csv(output_file_path, header=False, index=False)


if __name__ == '__main__':
    args = read_args()
    config = read_config_file(args['conf'], ".")

    original_results_path = Path(args['original'])
    result_files = enumerate_results(original_results_path)

    if len(result_files) == 0:
        print(
            f"far_rerank: No original results found in {original_results_path}"
        )

    dest_results_path = Path(args['result'])

    data_dir = single_xpath(config.get_xml(),
                            '/librec-auto/data/data-dir').text

    data_path = Path(data_dir)
    data_path = data_path.resolve()

    item_feature_df = load_item_features(config, data_path)
    if item_feature_df is None:
        exit(-1)

    helper = setup_helper(args, config, item_feature_df)

    split_path = data_path / 'split'
    pat = re.compile(RESULT_FILE_PATTERN)

    for file_path in result_files:

        # reading the training set
        m = re.match(pat, file_path.name)
        cv_count = m.group(1)

        tr_df = load_training(split_path, cv_count)
        if tr_df is None:
            exit(-1)

        print(f'Load results from {file_path}')
        results_df = pd.read_csv(file_path,
                                 names=['userid', 'itemid', 'score'])

        reranked_df = execute(results_df, tr_df, helper)
        output_reranked(reranked_df, dest_results_path, file_path)
