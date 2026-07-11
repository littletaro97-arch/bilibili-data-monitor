# v0.11.1 real-device checklist

1. Open Settings and confirm the visible groups are System permissions, Crawl strategy and History data management; confirm version 0.11.1 remains at the bottom.
2. Import a valid ZIP. The confirmation dialog must close after the transaction and the result must show added videos, snapshots, duplicates and rejected records.
3. Import the same ZIP again. It must add zero duplicate snapshots and must not start two jobs after rapid taps.
4. Cancel the system file picker. No error should appear and no data should change.
5. Open Settings, Advanced, Detail and History; system back must return Home. Back on Home must use the normal Android exit/background behavior.
6. With an import dialog or interval editor open, back must close that overlay before navigating Home.
7. Start continuous monitoring. The Background running notification must remain present. Stop monitoring and confirm it disappears.
8. Send a test notification. It must appear on the Data alerts channel, be swipe-clearable and clearable via Clear all, and must not start collection.
9. Let continuous monitoring complete one cycle. A separate result notification should appear according to the alert settings while the background notification remains.
10. Change the phone zone between UTC, Asia/Shanghai, Asia/Seoul and America/New_York. Record count and ordering must remain unchanged while displayed labels update locally.
11. Import the same exchange ZIP before and after a zone change. The second import must not create time-zone duplicates.
12. Check History and Trend after the zone change; both must remain ordered by the actual collection instant.

Logs: filter Logcat by `MonitorNotification`, `ContinuousMonitoringService`, `exchange`, and `work`; technical state is also available under Advanced > Technical diagnostics.
