"""Task catalogue favorites, independent of queue and music favorites."""
import store

FILE = 'work-favorites.json'
MAX_FAVORITES = 5000


def _valid_key(key):
    return (isinstance(key, str) and 0 < len(key) <= 1000
            and key.startswith(('gather:', 'craft:', 'alter:'))
            and key.split(':', 1)[1].strip() != ''
            and not any(ord(c) < 32 for c in key))


def get_favorites():
    with store.LOCK:
        return _read()


def _read():
    result = {}
    for key, enabled in store._load_dict(FILE).items():
        if enabled is True and _valid_key(key):
            result[key] = True
            if len(result) >= MAX_FAVORITES:
                break
    return result


def set_favorite(key, enabled):
    if not _valid_key(key) or not isinstance(enabled, bool):
        raise ValueError('잘못된 작업 즐겨찾기 값입니다.')
    with store.LOCK:
        favorites = _read()
        if enabled:
            if key not in favorites and len(favorites) >= MAX_FAVORITES:
                raise ValueError('작업 즐겨찾기는 5,000개까지 저장할 수 있습니다.')
            favorites[key] = True
        else:
            favorites.pop(key, None)
        store.save(FILE, favorites)
        return favorites
