"""Locked, recoverable persistence for explicit song identity reconciliation."""
if __package__:
    from . import identity
else:
    import identity
import store  # Same shared module/LOCK as folio.engine (app is on sys.path).

JOURNAL = 'folio/identity-recovery.json'
FILES = {
    'songs': 'folio/songs.json', 'favorites': 'folio/favorites.json',
    'song_instruments': 'folio/song_instruments.json', 'recent': 'folio/recent.json',
    'playlists': 'folio/playlists.json', 'presets': 'folio/presets.json',
    'ens': 'folio/ens.json', 'durations': 'folio/durations.json',
    'artists': 'folio/artists.json',
}


def recover():
    """Rollback an interrupted migration; safe to repeat after another failure.

    Integrator MUST call before any folio state read/write at startup. If a
    rollback cannot complete, propagate the error and keep journal for retry;
    never allow newer writes to race with pending recovery.
    """
    with store.LOCK:
        journal = store.load(JOURNAL, {})
        if not journal:
            return False
        before = journal.get('before') if isinstance(journal, dict) else None
        if not isinstance(before, dict) or set(before) != set(FILES):
            raise ValueError('invalid identity recovery journal')
        for name, path in FILES.items():
            store.save(path, before[name])
        store.save(JOURNAL, {})
        return True


def candidates(visible_keys):
    with store.LOCK:
        recover()
        return identity.rename_candidates(store.get_songs(), visible_keys)


def apply(old_key, new_item, visible_keys):
    """Persist a user-confirmed rename, return migrated song record.

    Caller must stop music queue first and hold its command/engine serialization
    lock. visible_keys MUST come from current engine library, never client data.
    Raises ValueError for stale selections or conflicting target settings.
    """
    visible = set(visible_keys)
    if old_key in visible:
        raise ValueError('original song is still in bag')
    if not isinstance(new_item, dict) or new_item.get('key') not in visible:
        raise ValueError('target song is not in bag')
    with store.LOCK:
        recover()
        before = {name: store.load(path, [] if name == 'recent' else {})
                  for name, path in FILES.items()}
        # Normalize songs only for validation/plan; preserve exact on-disk backup.
        state = dict(before)
        state['songs'] = store.get_songs()
        after = identity.plan_rename(state, old_key, new_item)
        store.save(JOURNAL, {'version': 1, 'before': before})
        try:
            for name, path in FILES.items():
                store.save(path, after[name])
            # This is the commit point. If interrupted before it, startup rolls
            # back the entire snapshot; no partial migration is accepted.
            store.save(JOURNAL, {})
        except Exception:
            recover()
            raise
        return after['songs']['songs'][new_item['key']]
