"""Pure, explicit song-rename planning and cached inventory observation.

No IO or game commands. Callers must lock, revalidate and atomically persist the
returned snapshot. Raw game scores currently expose no stable instance ID, so
similar titles MUST NOT be treated as proof of identity.
"""
from copy import deepcopy
import hashlib
import json


def rename_candidates(songs, visible_keys):
    """Missing records offered for user confirmation, never auto-selected."""
    visible = set(visible_keys)
    return [deepcopy(r) for k, r in songs.get('songs', {}).items()
            if k not in visible and '#unlinked-' not in k]


def plan_rename(state, old_key, new_item):
    """Return copied file snapshots with every supported reference migrated.

    state keys: songs, favorites, song_instruments, recent, playlists, presets,
    ens, durations, artists; optional queue (folio music queue, NOT work queue).
    Requires an explicit caller/user choice. Conflicting settings are rejected
    before any change. A fresh target song ID is archived, never reused.
    """
    result = deepcopy(state)
    new_key, new_title = new_item.get('key'), new_item.get('title')
    if not isinstance(old_key, str) or not old_key or not isinstance(new_key, str) or not new_key or not isinstance(new_title, str) or not new_title:
        raise ValueError('invalid song key/title')
    songs = result.get('songs', {}).get('songs', {})
    if old_key not in songs:
        raise ValueError('original song not found')
    if old_key == new_key:
        return result
    source = songs[old_key]
    old_title = source.get('title') or old_key
    for field in ('favorites', 'song_instruments', 'ens'):
        values = result.get(field, {})
        if old_key in values and new_key in values and values[old_key] != values[new_key]:
            raise ValueError('conflicting ' + field)
    by = result.get('presets', {}).get('by_song', {})
    if old_key in by and new_key in by and by[old_key] != by[new_key]:
        raise ValueError('conflicting song preset')
    target = songs.get(new_key)
    if target:
        if any(target.get(k) for k in ('cover', 'cover_src', 'plays')):
            raise ValueError('target already has song history or cover')
        archived = new_key + '#unlinked-' + str(target['id'])
        if archived in songs:
            raise ValueError('archive key collision')
        target['key'], target['gone'] = archived, True
        songs[archived] = target
    songs.pop(old_key)
    source.update(key=new_key, title=new_title, gone=False)
    for field in ('song', 'artist'):
        if field in new_item:
            source[field] = new_item[field]
    songs[new_key] = source

    def move(values, a, b):
        if a not in values:
            return
        # Rebuild rather than pop/append: preserve favorite ordering.
        rebuilt = {b if k == a else k: v for k, v in values.items() if k != b or a == b}
        values.clear()
        values.update(rebuilt)

    for field in ('favorites', 'song_instruments', 'ens'):
        move(result.setdefault(field, {}), old_key, new_key)
    move(by, old_key, new_key)
    # Title-keyed metadata is ambiguous when two records share a title.
    unique_title = not any(k != new_key and r.get('title') == old_title and '#unlinked-' not in k for k, r in songs.items())
    if unique_title:
        for values in (result.get('durations', {}), result.get('artists', {}).get('assign', {})):
            if old_title in values and new_title in values and values[old_title] != values[new_title]:
                raise ValueError('conflicting title metadata')
            move(values, old_title, new_title)

    def entries(items):
        for i, row in enumerate(items):
            if isinstance(row, str):
                if unique_title and row == old_title:
                    items[i] = {'key': new_key, 'title': new_title, 'inst': ''}
            elif isinstance(row, dict) and (row.get('key') == old_key or
                    (not row.get('key') and unique_title and row.get('title') == old_title)):
                row.update(key=new_key, title=new_title)
    entries(result.get('recent', []))
    entries(result.get('queue', []))
    for playlist in result.get('playlists', {}).get('playlists', []):
        entries(playlist.get('items', []))
    return result


def inventory_fingerprint(scores, instruments):
    """Order-independent cached snapshot hash, duplicates preserved."""
    def canonical(rows):
        return sorted(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(',', ':')) for r in rows)
    payload = json.dumps([canonical(scores), canonical(instruments)], ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


class InventoryRefreshGate:
    """Rate-limit a caller's idle-only refresh; never starts commands itself."""
    def __init__(self, interval=60):
        self.interval = max(15, float(interval))
        self.last_attempt = None
        self.inflight = False
        self.fingerprint = None

    def begin(self, now, *, connected, queue_busy, music_busy, command_busy):
        if self.inflight or not connected or queue_busy or music_busy or command_busy:
            return False
        if self.last_attempt is not None and now - self.last_attempt < self.interval:
            return False
        self.last_attempt, self.inflight = now, True
        return True

    def finish(self, scores=None, instruments=None, *, success=True):
        self.inflight = False
        if not success or scores is None or instruments is None:
            return False
        current = inventory_fingerprint(scores, instruments)
        changed = self.fingerprint is not None and self.fingerprint != current
        self.fingerprint = current
        return changed
