# 冻结实验协议与当前范围

当前 ISC113 只处理新 DailyDialog 的 A→B。data/confirmatory_dailydialog300.json 是原始冻结 300 段；主分析排除 train_5847、train_9210 后为 298 段。抽样来源、seed、排重和来源哈希保留于 data/split_manifest.json。该清单描述当时的历史抽样，不再运行或依赖开发集。

六方法是 direct_thinking、direct_multisample_verifier、route1_only、route2_only、dual_without_verifier、dual_with_verifier。dual 指两条推理路线，不表示双向预测。方法定义见 inference.py，原始提示词见 prompts.py。

供应商接口和历史标识符保留在 client.py：qwen3.8-flash，enable_thinking=true，thinking_budget=512，生成 max_tokens=2048，判别 max_tokens=3072，常规 temperature=0，第二次 direct 采样为 0.7。最多三次通信/结构失败重试；引用错误保留为实验结果，不能为获得更好引用重采样。400 内容拒绝不改写请求绕过。未知计费状态的中断请求禁止自动重发。

推断只接收五个字段：item_id、dialogue_id、direction、dataset、visible_turns。direction 必须是 A_to_B，原始 A turn_id 必须为正奇数、唯一且有序。完整 B、参考、真值和分级不进入推断请求。

原始算法配置见 runs/main/method_manifest.json；该文件是历史记录，代码哈希不代表重构后的文件。原始与重构后的代码哈希可由 audit/cleanup_manifest.json 对照。重构只增加范围及安全校验，提示词和六算法结果逻辑保持，298 段原始响应完整重放通过。

原始失败重试属于指定一轮的成本依据，保留于日志。其他实验、反向数据、冗余导出、旧一次性脚本和缓存已清理。清理范围仅为本 isc113 目录，未另建备份。
