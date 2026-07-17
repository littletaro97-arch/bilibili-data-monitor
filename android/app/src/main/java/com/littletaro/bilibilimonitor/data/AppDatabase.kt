package com.littletaro.bilibilimonitor.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [VideoEntity::class, VideoSnapshotEntity::class, AppLogEntity::class],
    version = 5,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun dao(): MonitorDao

    companion object {
        fun create(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "bilibili_monitor.db")
                .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)
                .build()

        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL(
                    "ALTER TABLE video_snapshots ADD COLUMN captureSource TEXT NOT NULL DEFAULT 'UNKNOWN'"
                )
            }
        }

        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE video_snapshots ADD COLUMN exchangeDigest TEXT")
            }
        }

        val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE videos ADD COLUMN coverUrl TEXT")
                database.execSQL("ALTER TABLE video_snapshots ADD COLUMN collectedAtEpochMillis INTEGER NOT NULL DEFAULT 0")
                database.execSQL(
                    "UPDATE video_snapshots SET collectedAtEpochMillis = " +
                        "COALESCE(CAST(strftime('%s', collectedAt) AS INTEGER) * 1000, 0)"
                )
                database.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_video_snapshots_bvId_collectedAtEpochMillis_id " +
                        "ON video_snapshots (bvId, collectedAtEpochMillis, id)"
                )
            }
        }

        val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE videos ADD COLUMN deletedAt TEXT")
                database.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_videos_deletedAt_updatedAt " +
                        "ON videos (deletedAt, updatedAt)"
                )
            }
        }
    }
}
