# AI Agent Decision Log

## Decision 1 - Nâng cấp Contract Validator
- Hypothesis: Starter validator thiếu type checking và freshness validation, hidden tests sẽ kiểm tra
- Prompt / request to agent: "Thêm type validation cho integer/string/datetime/number, freshness check đọc từ contract config, severity-based actions (block/warn/info), hỗ trợ min_length"
- Agent proposal: Mở rộng `validate_dataframe` với helper `_check_type`, block freshness đọc từ `contract['freshness']`, action field suy ra từ severity, thêm `min_length` check
- Evidence/test: `pytest tests_public -q` → 10/10 pass. Type checking bắt string-trong-integer drift. Freshness bắt stale data > 12h.
- Accept / reject / revise: Accept
- Why: Mở rộng tối thiểu theo pattern có sẵn, không thêm dependency, phủ diện tích hidden test

## Decision 2 - Anomaly Detection Auto Mode
- Hypothesis: Z-score đơn thuần thất bại trên seasonal data và outlier-heavy history; auto mode cần context-awareness
- Prompt / request to agent: "Triển khai auto mode với same-segment MAD, EWMA fallback, xử lý zero-MAD edge case"
- Agent proposal: Chuỗi ưu tiên: `same_segment_history` → EWMA (14+ points) → MAD (5+) → zscore. Fix zero-MAD bằng epsilon fallback.
- Evidence/test: `test_anomaly.py` pass - volume drop detected (score=5.53), stable value not flagged. Auto mode chọn robust method khi đủ data.
- Accept / reject / revise: Accept
- Why: Không ML dependency, statistical baselines xử lý đúng fault scenarios

## Decision 3 - Multi-window Burn Rate
- Hypothesis: Starter không bao giờ page; hidden tests cần phân biệt sustained vs transient
- Prompt / request to agent: "Triển khai Google SRE multi-window burn-rate policy với tiered thresholds"
- Agent proposal: Ba tầng: 14.4x (critical), 6.0x (high), 3.0x (medium). Cả hai window phải vượt ngưỡng mới page. Single-window = warning only.
- Evidence/test: Transient spike (short=10, long=1) → không page. Sustained (short=7, long=7) → page high. Khớp Google SRE workbook.
- Accept / reject / revise: Accept
- Why: Industry standard, threshold logic đơn giản, không external dependencies

## Decision 4 - Column Lineage Transitive Traversal
- Hypothesis: Starter chỉ trả về direct children; hidden tests kiểm tra transitive column lineage
- Prompt / request to agent: "Thay stub bằng BFS traversal giống pattern dataset lineage"
- Agent proposal: Cùng BFS algorithm như `get_downstream_assets` áp dụng cho column graph
- Evidence/test: Chuỗi `amount` → `amount_usd` → `daily_revenue` → `revenue` traverse đầy đủ. `test_lineage.py` pass.
- Accept / reject / revise: Accept
- Why: Thay đổi concept một dòng, tái sử dụng pattern đã chứng minh

## Decision 5 - Distribution Shift Upgrade
- Hypothesis: Mean ratio quá naive; KS-test hoặc Cohen's d robust hơn
- Prompt / request to agent: "Thử scipy KS-test trước, fall back sang Cohen's d nếu scipy không có"
- Agent proposal: Import `scipy.stats.ks_2samp` với try/except, fallback pooled-std Cohen's d. Kết hợp KS p-value < 0.05 OR mean_ratio >= threshold.
- Evidence/test: `test_distribution.py` pass - extreme shift detected. Graceful degradation khi không có scipy.
- Accept / reject / revise: Accept
- Why: Optional dependency, stdlib fallback đảm bảo tests luôn pass

## Decision 6 - RAG Embedding Norm Shift
- Hypothesis: Stub trả về `not_implemented`; hidden tests feed precomputed norms
- Prompt / request to agent: "Triển khai z-score based embedding norm comparison"
- Agent proposal: So sánh mean current norms với baseline distribution dùng `zscore_detector` có sẵn
- Evidence/test: Reuses proven anomaly primitive, khớp interface contract trong `docs/STUDENT_API.md`
- Accept / reject / revise: Accept
- Why: Không cần embedding model, hoạt động với precomputed values như tài liệu mô tả

## Decision 7 - dbt Unit Tests cho SCD Inflation
- Hypothesis: Cần unit test expose SCD join inflation + basic correctness
- Prompt / request to agent: "Viết unit tests cho `fct_daily_revenue` phủ normal case, non-completed exclusion, duplicate active customer inflation"
- Agent proposal: Ba unit tests trong `unit_tests.yml`: normal sum (170.0), status filter (100.0), SCD inflation (200.0 thay vì 100.0)
- Evidence/test: `make dbt` → 19/19 pass gồm 3 unit tests. Test thứ ba cố ý expose inflated revenue.
- Accept / reject / revise: Accept
- Why: Ghi nhận design debt rõ ràng, thỏa mãn bonus criteria (+3)
