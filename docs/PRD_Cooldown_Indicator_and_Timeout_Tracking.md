# PRD: Job Cooldown Visual Indicator and Timeout Status Tracking

## Problem Statement

Currently, when a task execution completes, system operators on the dashboard settings page have no visibility into the "cooldown" state of that job. If the job completes or times out, the operator might try to trigger the task again or wonder why a volume trigger isn't starting it, not realizing that it is currently in its rest period (cooldown). Furthermore, if a job run is terminated due to exceeding its maximum duration (Timeout), the status is stored in the database's TaskRun history as "timeout", but the JobConfig configuration's last run status still displays as "Success", which is misleading.

## Solution

1. **Explicit Timeout Status**: Update the scheduler wrapper so that if a task execution is aborted due to a timeout, the `last_run_status` on the job configuration is marked as `"timeout"` instead of defaulting to `"success"`.
2. **Visual Cooldown Indicator**: Expose the job's cooldown state via the FastAPI backend (`in_cooldown` and `cooldown_remaining_seconds`).
3. **Settings Dashboard UI Badge**: Update the settings page so that the job card displays an amber/yellow "Timeout" badge if it timed out, and dynamically shows a live-ticking cooldown countdown (e.g. `Cooldown (2m 14s left)`) when the job is in its rest period.

## User Stories

1. As a system operator, I want to see a clear "Timeout" status badge on a job card when it is terminated due to exceeding its maximum execution duration, so that I know it was partially completed rather than fully successful.
2. As a system operator, I want to see an "In Cooldown" indicator on the job configuration card while a job is resting, so that I know why a volume-based or scheduled trigger is not executing the job.
3. As a dashboard user, I want the cooldown remaining timer to tick down live in real-time, so that I can see exactly when the job will be eligible to run again without manually refreshing the page.
4. As a developer, I want the API `/api/scheduler/jobs` to return structured fields for `in_cooldown` and `cooldown_remaining_seconds`, so that the frontend can determine the exact remaining time without client-side timezone math.
5. As a system administrator, I want manual triggers to bypass the cooldown guard even when the UI displays the cooldown indicator, so that I can force-run a task in an emergency.

## Implementation Decisions

- **Backend API Contract**: `JobConfigResponse` will include `in_cooldown` (boolean) and `cooldown_remaining_seconds` (integer).
- **Timeout Logging**: Modify the background runner wrapper to fetch the matching `TaskRun` record at the end of the run. If the status in `TaskRun` was updated to `"timeout"`, set `JobConfig.last_run_status` to `"timeout"`.
- **Frontend Live Timer**: `JobCard` will implement a local React interval hook to decrement `cooldown_remaining_seconds` every second, updating the display text dynamically.
- **Frontend Status badges**: Define a new styling variant (yellow/amber warning background with warning or clock icon) for the `"timeout"` status.

## Testing Decisions

- A good test targets external behavior rather than implementation details.
- We will test the scheduler API endpoint to verify that when `last_run_time` is set and within `cooldown_minutes`, the `in_cooldown` field is returned as `true` and the correct remaining seconds are computed.
- Prior art: Refer to `tests/test_api_news_extended.py` for API routes testing pattern, and `tests/test_cooldown.py` for scheduler wrapper mocking.

## Out of Scope

- WebSocket-based push updates for cooldown state (polling/local countdown is sufficient).
- Changing the 1-minute volume trigger check frequency.

## Further Notes

None.
