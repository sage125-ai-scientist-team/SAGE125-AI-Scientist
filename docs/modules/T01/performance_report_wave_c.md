# T01 Wave C 性能报告（本地微基准）

**Scope:** content-hash cache、bundle digest、quality gate、envelope serialize  
**Environment:** Windows 11 / PowerShell / CPython（以本机 `python` 为准）  
**Honesty:** 本报告为开发机微基准，不是跨机正式 SLA；不宣称生产 latency 达标。

## Method

```powershell
python -c @"
import time
from app.contracts.evidence import EvidenceCardContract, ClaimEvidenceLink, EvidenceBundle
from app.evidence.content_hash_cache import ContentHashCache, deterministic_bundle_digest
from app.evidence.quality_gate import run_quality_gate
from app.evidence.citation_renderer import build_citation_item
from app.evidence.serialization import build_output_envelope_v125, dumps_output_envelope

card = EvidenceCardContract(
    evidence_id='EV-P', source_id='s', source_type='paper', title='Perf',
    quoted_text='Performance quote text for local microbenchmark path.',
    locator={'page': 1}, authors=['A'], year=2024, doi='10.1/p',
    content_hash='sha256:p', domain='medicine',
)
bundle = EvidenceBundle(
    bundle_id='B-P', evidences=[card],
    links=[ClaimEvidenceLink(claim_id='C1', evidence_id='EV-P', relation='supports', claim_domain='medicine')],
)
cache = ContentHashCache()
t0 = time.perf_counter()
for _ in range(1000):
    cache.get_or_compute(card.quoted_text)
t1 = time.perf_counter()
for _ in range(200):
    deterministic_bundle_digest(bundle)
t2 = time.perf_counter()
for _ in range(200):
    run_quality_gate(bundle)
t3 = time.perf_counter()
env = build_output_envelope_v125(
    bundle=bundle,
    citations=[build_citation_item(claim_id='C1', card=card)],
    quality=run_quality_gate(bundle),
)
for _ in range(100):
    dumps_output_envelope(env)
t4 = time.perf_counter()
print({
    'cache_1000_s': round(t1-t0, 6),
    'digest_200_s': round(t2-t1, 6),
    'quality_200_s': round(t3-t2, 6),
    'dumps_100_s': round(t4-t3, 6),
    'cache_hits': cache.stats.hits,
})
"@
```

## Local measured result（本机一次实测）

| Op | Iterations | Seconds |
|---|---|---|
| cache get_or_compute | 1000 | 0.001667（hits=999） |
| deterministic_bundle_digest | 200 | 0.004414 |
| run_quality_gate | 200 | 0.001187 |
| dumps_output_envelope | 100 | 0.003331 |

说明：开发机微基准，不宣称跨机正式 SLA / 生产 latency 达标。
