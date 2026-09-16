# Versioning

v0.11.0 is a repository-wide release covering Android and Windows. Android uses versionName 0.11.0/versionCode 17. Windows release records use the same v0.11.0 label. History exchange has an independent integer `formatVersion`; this release supports formatVersion 1.

Never rewrite old tags or overwrite old release directories. Roll back source with the previous tag and export data before attempting an Android database downgrade.

## v0.11.1

Repository-wide patch release. Android uses `versionName 0.11.1` / `versionCode 18`; Windows release records use `v0.11.1`. Android Room remains v3, Windows SQLite remains `user_version=1`, and history exchange remains `formatVersion=1`.

## v0.11.2

Android-only patch release using `versionName 0.11.2` / `versionCode 19`. Room remains v3 and history exchange remains `formatVersion=1`; no database migration is required. Runtime schedule and countdown fields are stored in DataStore, not Room.

## v0.12.0

Android data-display release using `versionName 0.12.0` / `versionCode 20`. Room moves from v3 to v4 through a non-destructive migration that adds nullable `coverUrl` and absolute snapshot epoch milliseconds for correct database ordering. History exchange remains compatible `formatVersion=1`; the optional `coverUrl` field is understood by both Android and Windows and older exchange archives remain importable.

## v0.12.1

Android hotfix release using `versionName 0.12.1` / `versionCode 21`. Room remains v4 and history exchange remains `formatVersion=1`. The selected-video history Flow now moves absolute-time ordering to `Dispatchers.Default`, so list conversion cannot run on the Compose collection thread.
