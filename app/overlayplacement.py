"""Game-client-relative geometry without UI or activation calls."""
def clamp_band(x, y, width, height, game):
    if not game:
        return int(x), int(y)
    left, top, gw, gh = game
    return (int(max(left, min(x, left + max(0, gw - width)))), int(max(top, min(y, top + max(0, gh - height)))))

def popup_rect(band, size, game, gap=6):
    x, y, bw, bh = band[:4]
    vertical = len(band) > 4 and band[4] == 'vertical'
    width, height = size
    if not game:
        return (int(x + bw + gap), int(y), int(width), int(height)) if vertical else (int(x), int(y + bh + gap), int(width), int(height))
    left, top, gw, gh = game
    width, height = min(width, gw), min(height, gh)
    if vertical:
        right, left_room = max(0, left + gw - x - bw - gap), max(0, x - left - gap)
        leftward = width > right and left_room > right
        width = max(1, min(width, left_room if leftward else right))
        px = x - gap - width if leftward else x + bw + gap
        py = max(top, min(y, top + gh - height))
        return int(max(left, min(px, left + gw - width))), int(py), int(width), int(height)
    below, above = max(0, top + gh - y - bh - gap), max(0, y - top - gap)
    upward = height > below and above > below
    height = max(1, min(height, above if upward else below))
    px = max(left, min(x, left + gw - width))
    py = y - gap - height if upward else y + bh + gap
    return int(px), int(max(top, min(py, top + gh - height))), int(width), int(height)
