# VT-117: kiểm thử và tải giả lập

Baseline: 2a4bbc3b246e1f2c9b947a4d8de56489a4b37fc9. Patch: 6d9bf5f.

```powershell
python -m pytest backend/tests/unit/test_page_size_contract.py -q
$env:PYTHONPATH='backend'
python bt3/load_harness.py
```

Harness dùng ASGI cùng process, 120 coroutine, repository giả chờ 10ms. Không suy ra khả năng production. PostgreSQL test: xem backend/README.md; cần Docker daemon và TEST_DATABASE_URL. Logs fail trước patch và mutation ở thư mục gốc.
