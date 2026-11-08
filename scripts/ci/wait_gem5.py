# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
import sys
import time

from scripts.ci.ci_lifecycle import Lifecycle
from scripts.ci.image_artifact import github


PRODUCER = "Build gem5 (VEGA_X86)"


def wait_for_runtime(
    repository: str, run: int, attempt: int, timeout: int, lifecycle: Lifecycle,
) -> int:
    if timeout <= 0:
        raise ValueError("gem5 wait timeout must be positive")
    deadline = time.monotonic() + timeout
    endpoint = f"repos/{repository}/actions/runs/{run}"
    while time.monotonic() < deadline:
        lifecycle.check()
        pages = json.loads(github([
            f"{endpoint}/jobs?filter=all&per_page=100",
            "--paginate", "--slurp",
        ], lifecycle))
        jobs = [job for page in pages for job in page["jobs"]
                if job["name"] == PRODUCER and job["run_attempt"] <= attempt]
        producer = max(jobs, key=lambda job: job["run_attempt"], default=None)
        if producer and producer["status"] == "completed":
            conclusion = producer["conclusion"]
            if conclusion != "success":
                raise RuntimeError(f"gem5 producer ended with {conclusion}")
            # Failed-job reruns copy successful jobs into the new attempt,
            # preserving execution timestamps without publishing a new artifact.
            execution_attempt = min(
                job["run_attempt"] for job in jobs
                if (job["started_at"], job["completed_at"])
                == (producer["started_at"], producer["completed_at"])
            )
            name = f"gem5-runtime-{run}-{execution_attempt}"
            pages = json.loads(github([
                f"{endpoint}/artifacts?per_page=100&name={name}",
                "--paginate", "--slurp",
            ], lifecycle))
            artifacts = [item for page in pages for item in page["artifacts"]
                         if item["name"] == name]
            if len(artifacts) > 1:
                raise ValueError("ambiguous gem5 runtime artifacts")
            if artifacts:
                if artifacts[0]["expired"]:
                    raise ValueError("gem5 runtime artifact expired")
                lifecycle.check()
                return artifacts[0]["id"]
        remaining = deadline - time.monotonic()
        if remaining > 0:
            print(
                f"Waiting for gem5 run {run}, attempt {attempt}; "
                f"{remaining:.0f}s remaining", file=sys.stderr, flush=True,
            )
            time.sleep(min(10, remaining))
    raise TimeoutError(
        f"timed out waiting for gem5 run {run}, attempt {attempt}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    with Lifecycle().installed() as lifecycle:
        artifact = wait_for_runtime(
            os.environ["GITHUB_REPOSITORY"], int(os.environ["GITHUB_RUN_ID"]),
            int(os.environ["GITHUB_RUN_ATTEMPT"]), args.timeout, lifecycle,
        )
    print(f"artifact-id={artifact}")


if __name__ == "__main__":
    main()
