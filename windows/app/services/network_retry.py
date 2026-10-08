"""Transport recovery delays; explicit platform restrictions use their own cooldown."""
NETWORK_RETRY_DELAYS = (5, 10, 20, 40, 80, 160, 320, 600)


def network_retry_delay(failures):
    return NETWORK_RETRY_DELAYS[min(max(int(failures)-1,0),len(NETWORK_RETRY_DELAYS)-1)]
