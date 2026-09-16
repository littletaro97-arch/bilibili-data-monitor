# v0.11.2 real-device checklist

1. Start continuous monitoring at 1 minute, then change to 3 minutes. The existing background notification must update immediately to 3 minutes without a second notification.
2. Confirm the next collection begins on the new cycle and no 1-minute stale cycle also runs.
3. Change 3→15, 15→5 and 30→60 minutes. Check Advanced logs for one active mode and one unique WorkManager only.
4. With continuous monitoring off, confirm 1/3/5/10-minute settings are labelled foreground-only and stop when the app is not active.
5. Open a video detail page. Confirm separate Video information and Check timing cards, correct effective interval, remaining time, progress and expected next time.
6. Switch Home→Detail→History→Detail and background/restore the app. Countdown must recalibrate from the same absolute next time, not restart from a full cycle.
7. Test automatic checking off, currently checking, failure, background-limited and WorkManager waiting states; no false normal countdown should remain.
8. Open History. Every snapshot must start collapsed, show time/source/core metrics, and reveal all fields after Expand.
9. Expand several records, scroll away/back and insert a new snapshot. Expanded states must not move to other records.
10. Repeat detail/history checks on a small screen, large font and dark mode; verify scrolling and touch targets.
11. Lock the screen during continuous monitoring, restore it, and compare notification interval, snapshot timestamps and Advanced next-check state.

Logs: filter Logcat by `work`, `ContinuousMonitoringService`, `auto refresh rescheduled`, and inspect Advanced > Technical diagnostics.
