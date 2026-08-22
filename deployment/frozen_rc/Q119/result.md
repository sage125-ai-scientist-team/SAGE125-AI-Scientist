# Semantic and Logical Disconnection: Auditing the Relevance of Computer Science Evidence to the Question of Human Intelligence Limits

## Input Question
Is there a limit to human intelligence?

## Domain
Artificial Intelligence

## Validation Status
needs_data

## Problem Statement
The question asks whether human intelligence has an inherent biological or cognitive upper bound. The provided booklet excerpt cites rising IQ scores (Flynn effect) and expert opinions suggesting no known limit, but lacks empirical evidence from neuroscience or psychometrics. The available EvidenceCards are exclusively from Computer Science (software testing, GUI testing, feature selection, and philosophy of AI), creating a domain mismatch that prevents direct biological inference.

## Rationale
Since no allowed evidence provides direct neuroscientific data on human cognitive limits, the only scientifically rigorous approach is to validate the hypothesis that the current evidence set is semantically and logically disconnected from the target domain. This transforms the 'unknown' into a verifiable audit of evidence relevance, adhering to the constraint that no external facts can be introduced as established truth.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: 当前允许的EvidenceCards（EV-Q119-*）与'人类智力生物学上限'这一科学问题之间存在显著的语义与逻辑断层，无法作为构建或验证该问题因果机制的事实基础；该证据集仅支持对'智能测试方法论'的元分析，而非对'人类认知极限'的本体论探究。
- **Mechanism**: 基于EV-Q119-2652d091e68e78953e36523e中关于图灵测试测量的是'人性模式'而非'智能本质'的论述，结合EV-Q119-e71fb096535bd446786f4dbe、EV-Q119-70df9c6ca8b62a082f57dc83及EV-Q119-3a50fd36f4edef4bef3eda20中纯粹的软件工程与统计特征选择内容，形成如下推断链：现有证据全部聚焦于人工系统（软件/AI）的验证与优化技术，缺乏生物神经系统约束（如代谢率、神经元密度、遗传力）的实证数据。因此，从这些证据到'人类智力上限'的任何推论均构成范畴错误（Category Error）。
- **Falsifiable Prediction**: 若使用经神经科学/心理学专家校验的标准术语库（如'g-factor heritability', 'synaptic plasticity ceiling', 'metabolic constraint on cognition'）与允许证据进行语义相似度计算，其平均余弦相似度将显著低于跨学科关联阈值（<0.3）；且逻辑审计显示从证据前提推导至'人类智力上限'结论的有效推理路径数量为0。
- **Required Observations**: 使用Qwen-Embedding模型（锁定具体版本号及推理参数）计算四个EvidenceCards与专家校验后的目标领域关键词集的语义相似度分布；由两名独立领域专家对'证据->结论'的逻辑推导链进行盲审，记录逻辑断裂点数量；验证目标关键词库是否覆盖了认知神经科学与心理测量学的核心概念，以排除假阴性风险
- **Risk of Being Wrong**: 若存在未被识别的计算神经科学或AI认知建模文献被错误归类为纯CS软件测试文献，则可能低估证据的实际相关性。但基于当前quoted_text内容分析，此风险较低。主要风险在于语义嵌入模型对高度专业化术语的对齐能力不足，导致假阴性，需通过专家校验关键词库来缓解。

### Hypothesis 2
- **Hypothesis**: 人类智力的操作性定义受限于测试工具的文化与技术依赖性，而非生物认知能力的绝对上限；观察到的智力分数变化可能反映测试效度漂移，但该假设在当前证据下仅为待验证的元理论推测，缺乏直接心理测量学实证支持。
- **Mechanism**: 延伸EV-Q119-2652d091e68e78953e36523e中对图灵测试'测人性而非智能'的批判逻辑：若所有智能测试（包括IQ测试）都依赖于特定历史时期的知识模式与技术环境，则测试分数的上限反映的是测试设计的饱和度或文化适应性，而非大脑生理极限。然而，此机制链条缺少关键环节——即证明IQ测试确实存在类似图灵测试的'人性/文化偏差'而非'认知能力测量'的心理测量学证据。
- **Falsifiable Prediction**: 若未来引入的EvidenceCard包含跨文化、跨时代且内容无关的认知任务（如抽象推理、工作记忆广度）表现出稳定的渐近线或与生理指标（如脑容量、神经传导速度）显著相关，则该'测试效度假象'假设被削弱。
- **Required Observations**: 检索并验证是否存在涵盖心理测量学效度分析、g因子稳定性或弗林效应异质性的合格EvidenceCard；分析现有CS证据中是否有任何关于'测试偏差'或'测量饱和'的可迁移方法论洞见
- **Risk of Being Wrong**: 该假设本质上是将booklet中的观点（IQ上升）与唯一相关的哲学证据（EV-Q119-2652d091e68e78953e36523e）进行弱类比，缺乏直接事实支撑。若g因子被证明具有高度遗传稳定性且与环境无关，则此假设不成立。当前仅能作为低置信度的备选解释框架。

## Technical Details
本实验旨在验证推荐假设：'当前允许的EvidenceCards（EV-Q119-*）与人类智力生物学上限问题存在显著的语义与逻辑断层'。实验核心是通过计算语义相似度与逻辑审计，量化证据集在目标领域（神经科学/心理测量学）的覆盖缺失。

技术实现包括：
1. **语义嵌入与相似度计算**：使用 Qwen-Embedding 模型（具体版本需锁定，如 qwen-embed-v1.5）将四个 EvidenceCard 的全文文本及专家校验后的目标领域关键词库（Target Domain Keywords）映射到同一高维向量空间。计算每个 EvidenceCard 向量与目标领域质心向量的余弦相似度。
2. **逻辑推导审计**：构建形式化逻辑树，尝试从 EvidenceCard 的前提（如'图灵测试测人性'、'GUI测试方法'）推导至结论'人类智力存在/不存在生物学上限'。记录推导链条中的逻辑断裂点（Non-sequitur）数量。
3. **关键词库校验机制**：引入专家校验环节，确保目标关键词库（如 'g-factor heritability', 'synaptic plasticity ceiling'）覆盖认知神经科学核心概念，以排除因术语偏差导致的假阴性。
4. **基线对比**：设置随机 CS 论文基线与简单关键词匹配基线，以确认低相似度是领域错配而非模型偏差所致。

## Datasets
### Source


```json
[
  {
    "id": "EV-Q119-e71fb096535bd446786f4dbe",
    "description": "arXiv:1807.10953 - 软件测试突变检测研究",
    "domain": "Computer Science / Software Engineering"
  },
  {
    "id": "EV-Q119-70df9c6ca8b62a082f57dc83",
    "description": "arXiv:1202.4527 - GUI测试方法论",
    "domain": "Computer Science / Software Testing"
  },
  {
    "id": "EV-Q119-3a50fd36f4edef4bef3eda20",
    "description": "arXiv:2311.05033 - 无损特征选择统计测试",
    "domain": "Computer Science / Machine Learning Statistics"
  },
  {
    "id": "EV-Q119-2652d091e68e78953e36523e",
    "description": "arXiv:0712.3825 - 图灵测试哲学批判",
    "domain": "Computer Science / Philosophy of AI"
  }
]
```


### Target


```json
{
  "domain_keywords": [
    "g-factor heritability",
    "synaptic plasticity ceiling",
    "metabolic constraint on cognition",
    "neural density limits",
    "psychometric validity saturation"
  ],
  "expert_validation_status": "Pending expert review to ensure coverage of core neuroscience/psychometrics concepts."
}
```


## Paper Abstract
Background: The question of human intelligence limits is often discussed via IQ trends (Flynn effect), but empirical biological evidence is absent in the provided dataset. Methods: We hypothesize that the available EvidenceCards (focused on software testing and AI philosophy) are semantically disjoint from neuroscience domains. We employ Qwen-Embedding to calculate cosine similarities between evidence texts and expert-validated neuroscience keywords, alongside a blind logical audit of deduction paths. Validation Plan: Verify if similarity scores remain below threshold (<0.3) and if logical validity scores are negligible. Results: Pending execution of semantic embedding and expert logical audit experiments.

## Methods
1. Preprocess EvidenceCard texts and generate embeddings using locked Qwen-Embedding model. 2. Compute cosine similarity between evidence vectors and centroid of expert-validated neuroscience keyword vectors. 3. Conduct blind logical audit by two experts to identify valid/invalid inference steps from evidence to conclusion. 4. Ablation study removing philosophical evidence (EV-Q119-2652d091e68e78953e36523e) to assess impact on semantic proximity.

## Experiments
### Baselines


```json
[
  "Random CS Baseline: 随机选取非AI/测试领域的CS论文，预期相似度同样极低，确认领域间天然距离。",
  "Keyword Co-occurrence Baseline: 统计 EvidenceCard 中是否直接出现目标关键词（如 'brain', 'neuron'），预期频次接近零。"
]
```


### Metrics


```json
[
  "Mean Cosine Similarity: 证据与目标领域关键词质的平均余弦相似度。",
  "Logical Validity Score: 专家对逻辑推导链有效性的平均评分（1-5）。",
  "Evidence Coverage Ratio: 目标领域必要证据组件在允许证据集中的存在比例（预期为0）。",
  "False Negative Rate Estimate: 通过专家校验关键词库后，重新计算相似度以评估初始术语选择的偏差风险。"
]
```


### Ablation
移除 EV-Q119-2652d091e68e78953e36523e（图灵测试批判），仅保留纯软件工程证据（EV-Q119-e71fb096535bd446786f4dbe, EV-Q119-70df9c6ca8b62a082f57dc83, EV-Q119-3a50fd36f4edef4bef3eda20），观察语义相似度是否进一步降低至接近随机噪声水平。

### Validation Protocol
1. 双盲逻辑审计：两名专家独立评分，计算 Inter-rater Reliability (Kappa系数)。
2. 模型稳健性检查：使用备用嵌入模型（如 BGE-M3）复现相似度计算，确保结果不依赖于单一模型架构。
3. 关键词库迭代：邀请神经科学专家对目标关键词库进行两轮修订，确保无重大遗漏。

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q119-e71fb096535bd446786f4dbe** · arxiv · arXiv:1807.10953
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1807.10953.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:4|section:page-4|paragraph:1; content_sha256=f39b760eb0303236d9e53f63203e5f990089d6078816a35605e884b672aaf717
- **EV-Q119-70df9c6ca8b62a082f57dc83** · arxiv · arXiv:1202.4527
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1202.4527.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=eab2dd5e94a79797af716a47b3f90d0748af9f7fbf9dbff59b1ab38b633de88a
- **EV-Q119-3a50fd36f4edef4bef3eda20** · arxiv · arXiv:2311.05033
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2311.05033.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=2f7860c999131f6f0d0720303cf6e80bde32e8a6212b762460035dc2ef3639c0
- **EV-Q119-2652d091e68e78953e36523e** · arxiv · arXiv:0712.3825
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/0712.3825.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:3|section:page-3|paragraph:1; content_sha256=33b070bdd57d8b05a3bdf17afbbed6471fe3fe1f5dbca639472472246c708b57

## Reviewer Comments
- 修订版v2已成功整合上一轮评审的所有required_revisions：目标关键词库增加了专家校验环节（expert_validation_status: Pending），且Reproducibility Checklist明确锁定了Qwen-Embedding版本号与推理参数。
- 假设Hypothesis 0严格限定在allowed_evidence_ids范围内，将'证据不足'转化为可计算的语义断层验证任务，未引入任何外部神经科学事实作为既定前提，符合规则3与规则10。
- Results字段保持为'待执行验证实验'状态，未伪造任何相似度数值或逻辑审计结果，符合规则6。
- 实验设计包含明确的Baselines（Random CS, Keyword Co-occurrence）与Metrics（Mean Cosine Similarity, Logical Validity Score），且数据集定义清晰区分了Source（4个EV-Q119-*）与Target（Domain Keywords），满足可证伪性与可复现性要求。
- 引用的Evidence IDs（EV-Q119-2652d091e68e78953e36523e等）均存在于输入EvidenceCatalog中，且quoted_text内容与假设机制描述一致，无虚构引用。

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- 锁定 Qwen-Embedding 模型的具体版本号（如 qwen-embed-v1.5）及推理参数（temperature=0, top_p=1.0）。
- 提供所有 EvidenceCard 的 SHA-256 内容哈希值，确保文本源一致。
- 公开经专家校验的目标领域关键词库完整列表及其修订历史。
- 提供逻辑审计的结构化评分模板与专家资质说明。
- 代码仓库包含完整的预处理、嵌入计算、相似度分析及统计检验 Pipeline。

