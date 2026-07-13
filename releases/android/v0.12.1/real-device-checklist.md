# v0.12.1 real-device checklist

1. For a video with 5,000 or more snapshots, enter History and repeatedly switch 20 / 50 / 全部 while scrolling the list. Confirm there is no visible main-thread stall.
2. Verify absolute-time ordering across UTC and offset-bearing imported snapshots, including same-time records resolved by stable ID.
3. Re-run the v0.12.0 checklist for sampled trends, ratio charts, snapshot deltas and cover fallback; this hotfix must not regress them.
