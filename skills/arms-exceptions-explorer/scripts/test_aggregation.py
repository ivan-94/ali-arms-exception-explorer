from __future__ import annotations

import unittest

from arms_exceptions.app import (
    error_events_from_span,
    extract_top_stack_frame,
    fingerprint_from_tags,
    normalize_message,
    spans_from_get_trace_response,
)


def build_span(message: str = "bad user id 2038896274814722049", lineno: str = "42"):
    return spans_from_get_trace_response(
        {
            "Spans": [
                {
                    "TraceID": "trace-1",
                    "SpanId": "span-1",
                    "ServiceName": "ai-service-dev",
                    "OperationName": "POST /ai",
                    "ResultCode": "-1",
                    "TagEntryList": [
                        {"Key": "exception.type", "Value": "ValueError"},
                        {"Key": "exception.message", "Value": message},
                        {"Key": "exception.stacktrace", "Value": "Traceback (most recent call last):\n  File \"/app/main.py\", line 42, in handler\nValueError: bad user id"},
                        {"Key": "code.filepath", "Value": "/app/main.py"},
                        {"Key": "code.function", "Value": "handler"},
                        {"Key": "code.lineno", "Value": lineno},
                    ],
                }
            ]
        },
        trace_id="trace-1",
    )[0]


class AggregationTests(unittest.TestCase):
    def test_extracts_log_event_stacktrace_first(self) -> None:
        spans = spans_from_get_trace_response(
            {
                "Spans": [
                    {
                        "TraceID": "trace-1",
                        "SpanId": "span-1",
                        "ServiceName": "ai-service-dev",
                        "OperationName": "run/ai_daily.generate_report",
                        "TagEntryList": [
                            {"Key": "celery.exception_type", "Value": "ExecutorError"},
                            {"Key": "celery.einfo", "Value": "ExecutorError: wrapper failed"},
                        ],
                        "LogEventList": [
                            {
                                "Timestamp": 1780386659094,
                                "TagEntryList": [
                                    {"Key": "exception.type", "Value": "fastapi.exceptions.HTTPException"},
                                    {"Key": "exception.message", "Value": "422: abstract_text 或 abstract 至少需要提供一个"},
                                    {"Key": "exception.stacktrace", "Value": "Traceback (most recent call last):\n  File \"/app/voicemaster/public.py\", line 151, in get_recordings_by_date\nfastapi.exceptions.HTTPException: 422"},
                                    {"Key": "error.capture.source", "Value": "loguru.exception"},
                                    {"Key": "log.level", "Value": "ERROR"},
                                ],
                            }
                        ],
                    }
                ]
            },
            trace_id="trace-1",
        )

        events = error_events_from_span(spans[0], {"span-1"})

        self.assertEqual(events[0].exception_type, "fastapi.exceptions.HTTPException")
        self.assertIn("Traceback", events[0].stacktrace or "")
        self.assertEqual(events[0].top_stack_frame, "/app/voicemaster/public.py:get_recordings_by_date")

    def test_fingerprint_ignores_operation_and_lineno(self) -> None:
        first = fingerprint_from_tags(
            service_name="ai-service-dev",
            operation_name="POST /a",
            tags=build_span(lineno="42").tags,
            fallback_message="fallback",
        )
        second_tags = dict(build_span(lineno="99").tags)
        second = fingerprint_from_tags(
            service_name="ai-service-dev",
            operation_name="POST /b",
            tags=second_tags,
            fallback_message="fallback",
        )

        self.assertEqual(first.key, second.key)

    def test_message_normalization_removes_dynamic_values(self) -> None:
        normalized = normalize_message(
            "GET https://example.com/a?traceId=abc&x=1 failed id 2038896274814722049 uuid 123e4567-e89b-12d3-a456-426614174000 ptr 0x7ff"
        )

        self.assertIn("?<query>", normalized)
        self.assertIn("<long-number>", normalized)
        self.assertIn("<uuid>", normalized)
        self.assertIn("0x<hex>", normalized)

    def test_top_stack_frame_skips_common_framework_frames(self) -> None:
        stacktrace = (
            "Traceback (most recent call last):\n"
            "  File \"/app/main.py\", line 10, in handler\n"
            "  File \"/opt/venv/lib/python3.11/site-packages/fastapi/routing.py\", line 1, in app\n"
            "ValueError: failed"
        )

        self.assertEqual(extract_top_stack_frame(stacktrace), "/app/main.py:handler")


if __name__ == "__main__":
    unittest.main()
