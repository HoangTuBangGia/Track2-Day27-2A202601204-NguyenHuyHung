# Incident Report

## Severity
P1 - Revenue data integrity + KB freshness impact trên support agent

## Summary
Pipeline báo SUCCESS nhưng CEO thấy revenue giảm bất thường và Support Agent trả policy refund cũ. Root cause: (1) volume drop trong orders ingestion (~75% mất), (2) stale KB documents không được phát hiện bởi baseline freshness check, (3) thiếu SCD guard gây join inflation risk.

## Detection
- Signal: Contract validation bắt duplicate PK; anomaly detection phát hiện volume drop (score=5.53); KB freshness failure (delay > 60 min)
- First observed time: Khi chạy `make baseline` sau fault injection - duplicate_pk/volume_drop/stale_kb đều detect ngay

## Root Cause
1. **Volume drop**: upstream order ingestion mất ~75% bản ghi (fault injection mô phỏng partial ETL failure)
2. **Stale KB**: timestamp `published_at` bị lùi 3 giờ, vượt quá SLA freshness 60 phút
3. **Missing SCD guard**: `fct_daily_revenue` LEFT JOIN trên customers có thể inflate revenue nếu nhiều active rows tồn tại cho cùng customer

## Evidence
1. `detect_metric(300, [1000,1010,995,...])` → `is_anomaly=True`, score > 3.0 (volume drop detected)
2. Contract freshness check: delay > 30 min → failed; KB freshness: delay > 60 min → failed
3. Lineage BFS từ `stg_orders` → `[fct_daily_revenue, ceo_revenue_dashboard]`; SLO `burn_rate = 4.0x` tại target 99.5% với 2/100 bad events → breached

## Blast Radius

```text
raw_orders
-> stg_orders
   -> fct_daily_revenue
      -> ceo_revenue_dashboard

kb_documents
-> kb_active_docs
   -> rag_index
      -> support_agent

Column lineage:
raw_orders.amount -> stg_orders.amount_usd -> fct_daily_revenue.daily_revenue -> ceo_revenue_dashboard.revenue
kb_documents.content -> kb_active_docs.content -> rag_index.embedding -> support_agent.answer
```

## Mitigation
1. Block pipeline khi critical contract failures (`action=block` cho `severity=critical`)
2. Alert anomaly detection với context-aware baselines (same-weekday MAD, EWMA)
3. Thêm SCD uniqueness test trong dbt để ngăn join inflation
4. Triển khai KB freshness SLO với ngưỡng 60 phút
5. Multi-window burn-rate policy phân biệt transient spike vs sustained degradation

## Recovery
Chạy `make reset` để restore healthy baseline. Verify tất cả checks pass trước khi resume pipeline.

## Verification
- [x] Contract healthy - zero critical failures sau reset
- [x] dbt tests healthy - 19/19 pass (11 data tests + 3 unit tests + seeds + models)
- [x] Anomaly returned to expected range - stable value `is_anomaly=False`
- [x] SLO healthy / budget understood - `burn_rate < 1.0` khi healthy, multi-window policy hoạt động
- [x] Downstream output verified - blast radius traced, column lineage transitive

## Prevention / Action Items
| Action | Owner | Deadline | Why |
|---|---|---|---|
| Automated freshness monitoring cho tất cả critical datasets | Data Reliability Team | Sprint tới | Phát hiện stale data trước khi impact downstream |
| Multi-window burn-rate alerting | Data Reliability Team | Sprint tới | Giảm false positive từ transient spikes |
| Column-level lineage tracking | Data Engineering | Q4 2026 | Phân tích impact nhanh hơn khi incident xảy ra |
| Distribution drift detection (KS-test/Cohen's d) | Data Reliability Team | Sprint tới | Bắt metric shift mà mean ratio bỏ sót |
| RAG embedding norm shift detection | AI/ML Team | Q4 2026 | Đảm bảo chất lượng knowledge base cho support agent |
| Runbook cho mỗi alert | Data Reliability Team | Sprint tới | Giảm MTTR khi incident xảy ra |
