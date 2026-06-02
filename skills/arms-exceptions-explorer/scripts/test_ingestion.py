from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arms_exceptions.app import ServiceConfig, SyncOptions, TraceIngestionService, TraceRepository, resolve_window_ms


class FakeAliyunClient:
    def __init__(self, *, fail_services: set[str] | None = None) -> None:
        self.fail_services = fail_services or set()
        self.search_calls = 0
        self.get_trace_calls = 0

    def search_error_traces_by_page(self, **kwargs):
        self.search_calls += 1
        if kwargs["service_name"] in self.fail_services:
            raise RuntimeError("service failed")
        return {
            "PageBean": {
                "Total": 1,
                "TraceInfos": [
                    {
                        "TraceID": "trace-1",
                        "SpanID": "span-error",
                        "ServiceName": kwargs["service_name"],
                        "OperationName": "run/ai_daily.generate_report",
                        "Timestamp": 1780386659094,
                        "Duration": 80,
                    }
                ],
            }
        }

    def get_trace(self, **kwargs):
        self.get_trace_calls += 1
        return {
            "Spans": [
                {
                    "TraceID": kwargs["trace_id"],
                    "SpanId": "span-error",
                    "ServiceName": "ai-service-dev-celery-worker",
                    "OperationName": "run/ai_daily.generate_report",
                    "Timestamp": 1780386659094,
                    "Duration": 80,
                    "ResultCode": "-1",
                    "TagEntryList": [
                        {"Key": "celery.exception_type", "Value": "ExecutorError"},
                        {"Key": "celery.einfo", "Value": "Traceback (most recent call last):\n  File \"/app/ai_daily/report.py\", line 12, in generate_report\nExecutorError: failed 2038896274814722049"},
                        {"Key": "error.capture.source", "Value": "celery.task_failure"},
                    ],
                },
                {
                    "TraceID": kwargs["trace_id"],
                    "SpanId": "span-ok",
                    "ServiceName": "ai-service-dev-celery-worker",
                    "OperationName": "GET /health",
                    "ResultCode": "0",
                    "TagEntryList": [{"Key": "http.status_code", "Value": "200"}],
                },
            ]
        }


class IngestionTests(unittest.TestCase):
    def test_ingestion_persists_only_error_spans_and_groups(self) -> None:
        start_ms, end_ms = resolve_window_ms("1h")
        with tempfile.TemporaryDirectory() as tmp:
            repo = TraceRepository(Path(tmp) / "arms.sqlite")
            try:
                service = TraceIngestionService(client=FakeAliyunClient(), repository=repo)  # type: ignore[arg-type]
                summary = service.sync_errors(
                    SyncOptions(
                        target_name="ai-service-dev",
                        service=ServiceConfig(name="ai-service-dev-celery-worker"),
                        start_ms=start_ms,
                        end_ms=end_ms,
                    )
                )
                groups = repo.list_groups(target_name="ai-service-dev", service_names=["ai-service-dev-celery-worker"])
                occurrences = repo.list_group_occurrences(groups[0]["group_key"])
                span = repo.get_span("trace-1", "span-error")
                ok_span = repo.get_span("trace-1", "span-ok")
            finally:
                repo.close()

        self.assertEqual(summary.unique_traces, 1)
        self.assertEqual(summary.stored_spans, 1)
        self.assertEqual(summary.error_events, 1)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["occurrence_count"], 1)
        self.assertEqual(groups[0]["service_name"], "ai-service-dev-celery-worker")
        self.assertEqual(len(occurrences), 1)
        self.assertIsNotNone(span)
        self.assertIsNone(ok_span)


if __name__ == "__main__":
    unittest.main()
