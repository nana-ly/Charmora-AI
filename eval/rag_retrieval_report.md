# RAG Retrieval Eval Report

## Metrics

| metric | value |
| --- | ---: |
| case_pass_rate | 0.875 |
| hit@k | 0.8667 |
| recall@k | 0.8666666666666667 |
| category_hit_rate | 0.875 |
| brand_hit_rate | 1.0 |
| no_results_rate | 0.125 |
| unexpected_no_results_count | 1 |
| negative_exclusion_hit_rate | 1.0 |
| candidate_count_avg | 24.1875 |
| retrieved_count_avg | 2.625 |
| final_count_avg | 2.625 |

## Failed Cases

| case | failures | items |
| --- | --- | --- |
| negative_exclude_huawei_phone | unexpected no results<br>expected product not returned<br>expected category not returned |  |
| negative_exclude_specific_xiaomi | expected product not returned | p_digital_010 / 小米 MIX Fold 5 内折大屏旗舰折叠屏手机多任务办公影音利器 / 小米 / 1 / 10.0 / keyword<br>p_digital_009 / 小米 17 Max 大屏长续航高性能影音游戏5G智能手机12+256GB / 小米 / 2 / 9.0 / keyword<br>p_digital_011 / 小米平板 8 Pro 12.1英寸高刷大屏影音娱乐学习办公平板电脑 / 小米 / 3 / 1.0 / keyword |
