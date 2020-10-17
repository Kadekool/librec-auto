## NOTE: Masoud's code. Needs to be integrated into librec-auto-reranking framework


def find_short_head_split_point(sorted_list):
    s = 0.0
    eightyPercent = float(sum(sorted_list)) * 0.2
    for i in range(len(sorted_list)):
        s += sorted_list[i]
        if s >= eightyPercent:
            return i


def calc_ratio_popular(l, item_pops, LONG_TAIL_CUT):
    pops = [item_pops[i] for i in l if i in item_pops]
    populars = [x for x in pops if x > LONG_TAIL_CUT]
    return float(len(populars)) / len(l)


def calc_avg_pop(l, item_pops):
    sum_of_pop = sum([item_pops[i] for i in l if i in item_pops])
    return float(sum_of_pop) / len(l)


def user_cluster_pref(c, rated_items, cluster):
    user_cluster_prefs = []
    for item in rated_items:
        user_cluster_prefs.append(cluster[item])
    counts = Counter(user_cluster_prefs)
    return float(counts[c]) / sum(counts.values())


def write_to_file(output, f_name):
    f = open(f_name, "w")
    lines = output.split("\n")
    for line in lines:
        if ',' in line:
            f.write(line + "\n")


if __name__ == "__main__":
    train = pd.read_csv("train", sep='\t', names=['userid', 'itemid', 'rating'])
    train_item_popularity = train.groupby('itemid').size() / len(train.userid.unique())
    short_head_point = find_short_head_split_point(sorted(train_item_popularity.values, reverse=True))
    LONG_TAIL_CUT = sorted(train_item_popularity, reverse=True)[short_head_point]
    train['pop'] = train['itemid'].apply(lambda x: train_item_popularity[x])
    train['is_pop'] = train['pop'].apply(lambda x: x > LONG_TAIL_CUT)

    users = train.userid.unique()
    users_items_map = {}
    groupbyuser = train.groupby('userid')
    for user in users:
        users_items_map[user] = groupbyuser.get_group(user).itemid.tolist()
    users_popular_ratio_map = {}
    users_avgpop_map = {}
    for k, v in users_items_map.items():
        users_popular_ratio_map[k] = calc_ratio_popular(v, train_item_popularity, LONG_TAIL_CUT)
        users_avgpop_map[k] = calc_avg_pop(v, train_item_popularity)
    cluster = {}
    head = train[train['pop'] > LONG_TAIL_CUT]['itemid'].unique().tolist()
    tail = train[train['pop'] <= LONG_TAIL_CUT]['itemid'].unique().tolist()
    for i in head:
        cluster[i] = 0
    for i in tail:
        cluster[i] = 1

    # Add items in test set that do not exist in train set
    train_items = list(train.itemid.unique())
    test = pd.read_csv("test", sep='\t', names=['userid', 'itemid', 'rating'])
    test_not_in_train = list(test[~test.itemid.isin(train_items)].itemid.unique())
    for test_item in test_not_in_train:
        cluster[test_item] = 0

    user_pops = train.groupby('userid')['pop'].mean()
    # item_pops_map = train_item_popularity
    # users = train.userid.unique()

    input_long_rec_path = "rec-50"
    print("Input long rec path: " + input_long_rec_path)
    long_rec = pd.read_csv(input_long_rec_path, names=['userid', 'itemid', 'rating'], sep=',')
    # recs_reranking = pd.read_csv("Results_" + str(lp) + "/" + str(selected[0]) + "/rating-topn50/" + algname, sep=',', names=['userid', 'itemid', 'rating'])

    relevance_map = {}
    set_of_pairs = set()
    for index, row in long_rec.iterrows():
        relevance_map[(row['userid'], row['itemid'])] = row['rating']
        set_of_pairs.add((row['userid'], row['itemid']))

    train_items = train.itemid.unique()
    min_rating = long_rec['rating'].min()
    max_rating = long_rec['rating'].max()
    rating_scale = max_rating - min_rating
    long_rec['rating'] = long_rec['rating'].apply(lambda x: (x - min_rating) / rating_scale)
    pred_rel_map = {}
    for index, row in long_rec.iterrows():
        pred_rel_map[(row['userid'], row['itemid'])] = round(float(row['rating']), 8)
    users = long_rec.userid.unique()
    user_cluster_pref_map = {}
    for user in users:
        user_ratings = train[train.userid == user][['itemid', 'rating']]
        rated_items = user_ratings.itemid.tolist()
        if len(rated_items) != 0:
            user_cluster_pref_map[(user, 0)] = user_cluster_pref(0, rated_items, cluster)
            user_cluster_pref_map[(user, 1)] = user_cluster_pref(1, rated_items, cluster)

    list_of_S = []
    for user in users:
        S = []
        user_ratings = long_rec[long_rec.userid == user][['itemid', 'rating']]
        rated_items = user_ratings.itemid.tolist()
        R = user_ratings.itemid.tolist()
        clusters_covered = np.array(10)
        while len(S) < short_topN[0]:
            scores = []
            for r in R:
                relevance = pred_rel_map[(user, r)]
                if cluster[r] in clusters_covered:
                    ss = relevance + w * round(
                        float(len(np.where(clusters_covered != cluster[r]))) / len(clusters_covered), 8)
                else:
                    if r not in train_item_popularity:
                        train_item_popularity[r] = 0.0
                    ss = 1 - train_item_popularity[r]
                score = (1 - w) * relevance + w * ss
                scores.append(score)
            best_item = R[np.argmax(scores)]
            if (user, best_item) in set_of_pairs:
                true_relevance = relevance_map[(user, best_item)]
            else:
                true_relevance = 0
            S.append(str(user) + "," + str(best_item) + ',' + str(true_relevance))
            clusters_covered = np.append(clusters_covered, cluster[best_item])
            R.remove(best_item)
        list_of_S.append(S)
    output = ""
    for l in list_of_S:
        for s in l:
            output = output + s
            output = output + "\n"

    write_to_file(output, output_rec_path + "/" + output_rec_name)