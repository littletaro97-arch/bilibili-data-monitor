# Versioning

v0.11.0 is a repository-wide release covering Android and Windows. Android uses versionName 0.11.0/versionCode 17. Windows release records use the same v0.11.0 label. History exchange has an independent integer `formatVersion`; this release supports formatVersion 1.

Never rewrite old tags or overwrite old release directories. Roll back source with the previous tag and export data before attempting an Android database downgrade.

## v0.11.1

Repository-wide patch release. Android uses `versionName 0.11.1` / `versionCode 18`; Windows release records use `v0.11.1`. Android Room remains v3, Windows SQLite remains `user_version=1`, and history exchange remains `formatVersion=1`.
