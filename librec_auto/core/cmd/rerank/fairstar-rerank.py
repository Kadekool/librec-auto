## NOTE: Masoud's code. Needs to be integrated into librec-auto-reranking framework
import fairsearchcore as fsc

f=open("output","w")
# create the Fair object. k: size of long recommendation list, p: proportion of protected candidates in the topK elements (value should be between 0.02 and 0.98), alpha: significance level (value should be between 0.01 and 0.15)
fair = fsc.Fair(k, p, alpha)
# create an mtable using alpha unadjusted
mtable = fair.create_unadjusted_mtable()
# analytically calculate the fail probability
analytical = fair.compute_fail_probability(mtable)
# create an mtable using alpha adjusted
mtable = fair.create_adjusted_mtable()
# again, analytically calculate the fail probability
analytical = fair.compute_fail_probability(mtable)
for user in users:
	unfair_list = []
	# recommendation dataframe for "user" in long recommendation list. The variable items looks (user,items,score)
	items = groupby_users.get_group(user)
	rank = 1
	for i in range(len(items)):
		item = int(items.iloc[[i]].item)
		# The items score in FA*IR should be an integer number. So, I multiplied the score predicted by the base recommender by 100.
		score = int(float(items.iloc[[i]].rate)*100)
		# The variable "unprotected" is a list of unprotected items
		unfair_list.append(FairScoreDoc(item,score, False if item in unprotected else True))
	# let's check the ranking is considered fair
	fair.is_fair(unfair_list)
	# now re-rank the unfair ranking
	re_ranked = fair.re_rank(unfair_list)
	# 10 is the size of final recommendation list
	for j in range(10):
		# Users Id and Items Id in rating data and long recommendation lists should be mapped from 0 to the size of users and items, respectively.
		f.write(str(str(list(user_map)[list(user_map.values()).index(user)]))+','+str(list(item_map)[list(item_map.values()).index(re_ranked[j].id)])+","+str(re_ranked[j].score)+"\n")
f.close()
