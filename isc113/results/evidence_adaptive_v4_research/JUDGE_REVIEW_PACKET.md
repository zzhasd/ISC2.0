# 15 条严格命中翻转复核清单

同一预测文本与固定参考，不同候选集合语境下两次评审发生严格命中变化。以下列举只用于人工复核，不预设哪次正确。完整 A-only 上下文和参考见 JUDGE_REVIEW_PACKET.json。

## 1. train_7703

B was handing out nametags

v1: {'prediction_id': '4f9bef8e6ac040af0ad8478678bbec93723a7ec009cff499b504e1eec1a591cc', 'reference_ids': ['train_7703_A_to_B_a2_2'], 'relation': 'broader'}
v3: {'prediction_id': '4f9bef8e6ac040af0ad8478678bbec93723a7ec009cff499b504e1eec1a591cc', 'reference_ids': ['train_7703_A_to_B_a2_2'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。

## 2. train_1885

B has been reading the book since last night

v1: {'prediction_id': 'fce251fc04a1f0702a9b87b4ce92a871f00daa85eb2ef3e679ce469951d97342', 'reference_ids': ['train_1885_A_to_B_a1_1'], 'relation': 'narrower'}
v3: {'prediction_id': 'fce251fc04a1f0702a9b87b4ce92a871f00daa85eb2ef3e679ce469951d97342', 'reference_ids': ['train_1885_A_to_B_a1_1'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。

## 3. train_6802

B works as a fuel attendant at a gas station

v1: {'prediction_id': 'cbc89f2d53f2a11b59879a7d0bab81c724d4c5dd244de15d414d30ac7dff15c4', 'reference_ids': ['train_6802_A_to_B_a1_1'], 'relation': 'equivalent'}
v3: {'prediction_id': 'cbc89f2d53f2a11b59879a7d0bab81c724d4c5dd244de15d414d30ac7dff15c4', 'reference_ids': ['train_6802_A_to_B_a1_1'], 'relation': 'narrower'}

人工结论：待填写，不更改原表。

## 4. train_6833

B is canceling a reservation

v1: {'prediction_id': '4b4739f6cf6dc097f7033cebd6320b622b80941161f6e2cccf6d8febe517510f', 'reference_ids': ['train_6833_A_to_B_a1_1', 'train_6833_A_to_B_a2_1'], 'relation': 'broader'}
v3: {'prediction_id': '4b4739f6cf6dc097f7033cebd6320b622b80941161f6e2cccf6d8febe517510f', 'reference_ids': ['train_6833_A_to_B_a1_1', 'train_6833_A_to_B_a2_1'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。

## 5. train_3054

B has a hobby of photography

v1: {'prediction_id': 'f0c312dcb9a03e096b9cdd503b6a0ce94aa2911aea16330fe3b7d0fc4f1c282f', 'reference_ids': ['train_3054_A_to_B_a1_1'], 'relation': 'narrower'}
v3: {'prediction_id': 'f0c312dcb9a03e096b9cdd503b6a0ce94aa2911aea16330fe3b7d0fc4f1c282f', 'reference_ids': ['train_3054_A_to_B_a1_1'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。

## 6. train_10777

Daniel is young

v1: {'prediction_id': '1748ef87f2576d6ba8d17958aeba603f4d4308574f829ee9ee12e71899eb1aa3', 'reference_ids': ['train_10777_A_to_B_a2_1'], 'relation': 'equivalent'}
v3: {'prediction_id': '1748ef87f2576d6ba8d17958aeba603f4d4308574f829ee9ee12e71899eb1aa3', 'reference_ids': ['train_10777_A_to_B_a1_2', 'train_10777_A_to_B_a2_1'], 'relation': 'broader'}

人工结论：待填写，不更改原表。

## 7. train_11082

B has the ability to grant or deny unpaid leave to A

v1: {'prediction_id': 'a5e55ddef58524d66e7e9c2cd239f82410ad292af8359df9bb8b56f999805a4c', 'reference_ids': ['train_11082_A_to_B_a1_2'], 'relation': 'equivalent'}
v3: {'prediction_id': 'a5e55ddef58524d66e7e9c2cd239f82410ad292af8359df9bb8b56f999805a4c', 'reference_ids': ['train_11082_A_to_B_a1_2'], 'relation': 'narrower'}

人工结论：待填写，不更改原表。

## 8. train_7845

The person addressed is named Thomas

v1: {'prediction_id': '57a154a960718d68b22e02ece1de99a48bf4cdd26ed9723b53922d87e3e6bf79', 'reference_ids': ['train_7845_A_to_B_a1_1'], 'relation': 'equivalent'}
v3: {'prediction_id': '57a154a960718d68b22e02ece1de99a48bf4cdd26ed9723b53922d87e3e6bf79', 'reference_ids': ['train_7845_A_to_B_a1_1'], 'relation': 'broader'}

人工结论：待填写，不更改原表。

## 9. train_4293

B's rug was ruined by A spilling a drink on it

v1: {'prediction_id': '0fffa291cb16ea5ebd430e4cf8a8d87097ab6a075163ad95d0faac8e3424b879', 'reference_ids': ['train_4293_A_to_B_a1_1', 'train_4293_A_to_B_a2_1'], 'relation': 'narrower'}
v3: {'prediction_id': '0fffa291cb16ea5ebd430e4cf8a8d87097ab6a075163ad95d0faac8e3424b879', 'reference_ids': ['train_4293_A_to_B_a1_1'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。

## 10. train_3547

B worked with A at the same department before A's transfer last week

v1: {'prediction_id': 'edfaea44bb9f8ffe8c14a684cdd8c838e851319fc6325a995c224c1095daf907', 'reference_ids': ['train_3547_A_to_B_a1_2'], 'relation': 'equivalent'}
v3: {'prediction_id': 'edfaea44bb9f8ffe8c14a684cdd8c838e851319fc6325a995c224c1095daf907', 'reference_ids': ['train_3547_A_to_B_a1_2'], 'relation': 'narrower'}

人工结论：待填写，不更改原表。

## 11. train_10390

B likes the flower

v1: {'prediction_id': '5e17f60e99b8474e8d9d80759d5bb23d16f42d9fc845fa81d09ab85dd9a56f11', 'reference_ids': ['train_10390_A_to_B_a2_1'], 'relation': 'equivalent'}
v3: {'prediction_id': '5e17f60e99b8474e8d9d80759d5bb23d16f42d9fc845fa81d09ab85dd9a56f11', 'reference_ids': ['train_10390_A_to_B_a2_1'], 'relation': 'broader'}

人工结论：待填写，不更改原表。

## 12. train_10891

B's surname is Hughes

v1: {'prediction_id': '4f98322f617369f9a86d2699980515d8864d6d67d6b22249d8db1553cf9f6d71', 'reference_ids': ['train_10891_A_to_B_a1_1'], 'relation': 'equivalent'}
v3: {'prediction_id': '4f98322f617369f9a86d2699980515d8864d6d67d6b22249d8db1553cf9f6d71', 'reference_ids': ['train_10891_A_to_B_a1_1'], 'relation': 'broader'}

人工结论：待填写，不更改原表。

## 13. train_8867

B was positioned too close to the fireplace

v1: {'prediction_id': '26aa47e30710e8b641a3341a06e268ddf5ddd75073b4a79536c30a5f16d6e05f', 'reference_ids': ['train_8867_A_to_B_a1_1'], 'relation': 'broader'}
v3: {'prediction_id': '26aa47e30710e8b641a3341a06e268ddf5ddd75073b4a79536c30a5f16d6e05f', 'reference_ids': ['train_8867_A_to_B_a1_1'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。

## 14. train_6935

B suggested leaving a 20% tip

v1: {'prediction_id': '2239e6d6ea91da8ad1c6517dad6e6a3553222890dad1e25cc52884aac4cf7d6c', 'reference_ids': ['train_6935_A_to_B_a1_1'], 'relation': 'equivalent'}
v3: {'prediction_id': '2239e6d6ea91da8ad1c6517dad6e6a3553222890dad1e25cc52884aac4cf7d6c', 'reference_ids': ['train_6935_A_to_B_a1_1'], 'relation': 'broader'}

人工结论：待填写，不更改原表。

## 15. train_3188

B appears depressed

v1: {'prediction_id': 'db2441296cab22806ff1d68c43c6126ad66d2fcb6b5a68ad6a28ed0713536933', 'reference_ids': ['train_3188_A_to_B_a1_1', 'train_3188_A_to_B_a1_2'], 'relation': 'broader'}
v3: {'prediction_id': 'db2441296cab22806ff1d68c43c6126ad66d2fcb6b5a68ad6a28ed0713536933', 'reference_ids': ['train_3188_A_to_B_a1_2'], 'relation': 'equivalent'}

人工结论：待填写，不更改原表。
