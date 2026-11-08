# SPDX-License-Identifier: Apache-2.0

import json
import unittest
from unittest.mock import patch

from ci_lifecycle import Lifecycle
import wait_gem5


class Gem5ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.requests = []
        self.jobs = []
        self.artifacts = []
        self.enterContext(patch.object(
            wait_gem5.time, "monotonic", side_effect=lambda: self.now
        ))
        self.enterContext(patch.object(
            wait_gem5.time, "sleep", side_effect=self.advance
        ))
        self.enterContext(patch.object(
            wait_gem5, "github", side_effect=self.api
        ))

    def advance(self, seconds):
        self.now += seconds

    def api(self, arguments, lifecycle):
        lifecycle.check()
        self.requests.append(arguments)
        if "/runs/42/" in arguments[0] and "/jobs?" in arguments[0]:
            records = self.jobs.pop(0)
            return json.dumps([{"jobs": records}]).encode()
        self.assertIn("/runs/42/artifacts?", arguments[0])
        return json.dumps([{
            "artifacts": self.artifacts.pop(0),
        }]).encode()

    def job(self, status="completed", conclusion="success", attempt=2):
        return {"name": wait_gem5.PRODUCER, "status": status,
                "conclusion": conclusion, "run_attempt": attempt,
                "started_at": f"2026-11-08T0{attempt}:00:00Z",
                "completed_at": f"2026-11-08T0{attempt}:01:00Z"}

    def artifact(self, **changes):
        return {"id": 73, "name": "gem5-runtime-42-2",
                "expired": False, **changes}

    def wait(self, timeout=30, attempt=2):
        return wait_gem5.wait_for_runtime(
            "owner/repo", 42, attempt, timeout, Lifecycle()
        )

    def test_waits_for_success_and_the_current_attempt_artifact(self):
        self.jobs = [[], [self.job("in_progress", None)],
                     [self.job()], [self.job()]]
        self.artifacts = [[], [self.artifact(name="gem5-runtime-42-1"),
                              self.artifact()]]
        self.assertEqual(self.wait(timeout=40), 73)
        self.assertEqual(self.now, 30)
        self.assertTrue(all(
            request[0].startswith("repos/owner/repo/actions/runs/42/")
            for request in self.requests
        ))

    def test_failed_producer_never_supplies_a_runtime(self):
        for result in ("failure", "cancelled", "skipped", "timed_out"):
            with self.subTest(result=result):
                self.jobs = [[self.job(conclusion=result)]]
                self.artifacts = [[self.artifact()]]
                with self.assertRaisesRegex(RuntimeError, result):
                    self.wait()
                self.assertEqual(len(self.artifacts), 1)

    def test_retrying_only_failed_jobs_reuses_the_successful_producer(self):
        self.jobs = [[self.job(attempt=1)]]
        self.artifacts = [[self.artifact(name="gem5-runtime-42-1")]]
        self.assertEqual(self.wait(timeout=5), 73)
        self.assertIn("name=gem5-runtime-42-1", self.requests[-1][0])

    def test_copied_success_keeps_its_original_execution_artifact(self):
        original = {**self.job(attempt=1),
                    "started_at": "2026-11-08T09:41:43Z",
                    "completed_at": "2026-11-08T09:43:02Z"}
        copied = {**original, "run_attempt": 2}
        self.jobs = [[copied, original]]
        self.artifacts = [[self.artifact(name="gem5-runtime-42-1")]]
        self.assertEqual(self.wait(timeout=5), 73)
        self.assertEqual(self.now, 0)
        self.assertIn("name=gem5-runtime-42-1", self.requests[-1][0])

    def test_copy_of_a_rerun_uses_the_rerun_execution_artifact(self):
        rerun = self.job()
        copied = {**rerun, "run_attempt": 3}
        self.jobs = [[self.job(attempt=1), copied, rerun]]
        self.artifacts = [[self.artifact(name="gem5-runtime-42-1"),
                           self.artifact()]]
        self.assertEqual(self.wait(timeout=5, attempt=3), 73)
        self.assertIn("name=gem5-runtime-42-2", self.requests[-1][0])

    def test_actual_rerun_cannot_use_an_older_execution_artifact(self):
        self.jobs = [[self.job(attempt=1), self.job()]]
        self.artifacts = [[self.artifact(name="gem5-runtime-42-1")]]
        with self.assertRaises(TimeoutError):
            self.wait(timeout=5)

    def test_latest_failed_producer_cannot_fall_back_to_older_success(self):
        self.jobs = [[self.job(attempt=1), self.job(conclusion="failure")]]
        with self.assertRaisesRegex(RuntimeError, "failure"):
            self.wait()

    def test_does_not_consume_a_later_attempt(self):
        self.jobs = [[self.job(attempt=3)]]
        with self.assertRaises(TimeoutError):
            self.wait(timeout=5)

    def test_missing_producer_times_out(self):
        self.jobs = [[], []]
        with self.assertRaisesRegex(TimeoutError, "gem5"):
            self.wait(timeout=15)
        self.assertEqual(self.now, 15)

    def test_success_without_artifact_also_times_out(self):
        self.jobs = [[self.job()], [self.job()]]
        self.artifacts = [[], []]
        with self.assertRaises(TimeoutError):
            self.wait(timeout=15)

    def test_rejects_expired_or_ambiguous_artifacts(self):
        for records in ([self.artifact(expired=True)],
                        [self.artifact(), self.artifact(id=74)]):
            with self.subTest(records=records):
                self.jobs = [[self.job()]]
                self.artifacts = [records]
                with self.assertRaises(ValueError):
                    self.wait()

    def test_cancellation_prevents_any_request(self):
        lifecycle = Lifecycle()
        lifecycle.request("cancelled")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            wait_gem5.wait_for_runtime("owner/repo", 42, 2, 30, lifecycle)
        self.assertFalse(self.requests)


if __name__ == "__main__":
    unittest.main()
