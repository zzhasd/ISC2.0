# 新B（IA）独立重复实验

排除HW、HS、HU；全部15段对话均取另一侧A的全部话语。

改进版抽取算法自然输出128条，精确字符串去重后128项，汇总为34条画像；direct+thinking生成10条画像。

沿用已有改进提取算法和两路画像提示词，只有实际属性数量、伙伴标签元信息变化。两组均重新推理。抽取512/4096，画像生成2048/20000，qwen3.8-flash、temperature=0、enable_thinking=true。

两组生成均不读取自述或原子命题；direct仅输入全部A侧原话，无属性提取提示或中间清单。未开子代理、未评分。原属性和证据完整保留不保证自然语言总结语义无损，供人工审核。

文件：summary_portraits.md、direct_portraits.md、new_B_self_statements.md。

{
  "passed": true,
  "new_b": "IA",
  "all_A_only_sources_verified": true,
  "attributes": 128,
  "unique_strings": 128,
  "all_records_preserved": true,
  "no_archive_or_atoms_in_generation": true,
  "direct_no_extraction_prompt_or_input": true,
  "algorithm_and_config_unchanged_except_count_partner_metadata": true,
  "request_attempts": {
    "extraction": 79,
    "summary": 5,
    "direct": 3
  },
  "returned_usage": {
    "prompt_tokens": 254399,
    "total_tokens": 370868,
    "completion_tokens": 116469
  },
  "unknown_billing_attempts": 1,
  "excluded_previous_bs": [
    "HS",
    "HU",
    "HW"
  ],
  "summary_portraits": 34,
  "direct_portraits": 10,
  "archive_statements": 10,
  "credential_scan_passed": true,
  "no_agent_evaluation": true
}
