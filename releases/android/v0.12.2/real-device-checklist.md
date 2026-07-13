# v0.12.2 real-device checklist

1. Add two different BV videos, select different chart modes/metrics/ranges, leave and reopen each History page, then restart the app. Confirm settings restore per video with no cross-video leakage.
2. In ratio mode, check one combined chart contains numerator, denominator and ratio. Verify left/right axes, legend, 20 / 50 / 全部 switching, and a tap tooltip with timestamp, both raw values, ratio and manual/auto source.
3. Test zero and missing denominators: raw lines remain visible and the tooltip says the ratio cannot be calculated.
4. Verify no visible “已选”“已选择”“当前选择” remains in trend selectors; selected controls remain distinguishable and accessible.
5. Confirm a newly added video gains a cover after a successful refresh; verify offline, invalid URL and failed image requests show the stable placeholder without blocking video creation or refresh.
6. Exercise 5,000+ snapshots, fast range/mode changes, portrait/landscape, small screen, large font, dark mode, scrolling and app restart. Record any visible stutter or memory growth.
