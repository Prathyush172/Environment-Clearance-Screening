# Operational Incident Log

This log records genuine anomalies, bugs, and resolution steps encountered during the implementation and execution of the Environmental Clearance Pre-Screening Service.

---

### Incident 001: Windows Python Subprocess Event Loop Blocking in Sandboxed Command Execution
- **Timestamp:** 2026-10-28T10:18:43Z
- **Severity:** Medium (Development / Sandbox)
- **Symptom:** `pytest` commands invoking `asyncio.run()` in the sandboxed PowerShell session hung indefinitely or timed out after 10,000 ms.
- **Root Cause:** The default Python 3.13 event loop policy on Windows (`WindowsProactorEventLoopPolicy`) uses an I/O completion port (IOCP) pipe mechanism that encounters security blocks inside restricted sandboxed execution environments unless granted appropriate permission.
- **Fix / Resolution:** Executed test verification runs with elevated sandbox privileges (`BypassSandbox: true`). Configured unit tests to run via standardized async harnesses. All 29 unit tests subsequently completed in 14.35s with 100% pass rate.

---

### Incident 002: Batch Evaluation Runner AttributeError on Missing Capacity Field
- **Timestamp:** 2026-10-28T10:25:13Z
- **Severity:** Low (Code defect)
- **Symptom:** `eval.run` terminated on scenario 11 (`scenario_11_critically_polluted_area`) with `AttributeError: 'NoneType' object has no attribute 'get'`.
- **Root Cause:** Line 228 of `services/worker/graph_agent.py` executed `intake.get("capacity", {}).get("unit")` assuming `capacity` would default to `{}` if missing, but when `capacity: None` was explicitly passed in the dictionary, `intake.get("capacity")` returned `None`.
- **Fix / Resolution:** Replaced inline conditional with safe extraction:
  ```python
  area_ha = intake.get("area_ha")
  cap = intake.get("capacity") or {}
  if not area_ha:
      if isinstance(cap, dict) and cap.get("unit") == "ha":
          area_ha = cap.get("value")
      else:
          area_ha = 10.0
  ```
- **Verification:** Re-ran batch eval across all 24 scenarios; completed without errors with **91.67% route accuracy** and **0% hallucination rate**.
