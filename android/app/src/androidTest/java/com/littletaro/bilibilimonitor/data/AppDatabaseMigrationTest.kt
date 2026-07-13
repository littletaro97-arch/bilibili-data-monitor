package com.littletaro.bilibilimonitor.data

import android.content.Context
import androidx.room.Room
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AppDatabaseMigrationTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val name = "migration-v2-v4.db"

    @After fun cleanup() { context.deleteDatabase(name) }

    @Test fun migration2To4PreservesSnapshotAndAddsDigestCoverAndAbsoluteTime() {
        val config = SupportSQLiteOpenHelper.Configuration.builder(context).name(name).callback(object : SupportSQLiteOpenHelper.Callback(2) {
            override fun onCreate(db: SupportSQLiteDatabase) {
                db.execSQL("CREATE TABLE videos (bvId TEXT NOT NULL PRIMARY KEY, aid INTEGER, title TEXT, authorName TEXT, authorMid INTEGER, duration INTEGER, pubdate INTEGER, sourceUrl TEXT, createdAt TEXT NOT NULL, updatedAt TEXT NOT NULL)")
                db.execSQL("CREATE TABLE video_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, bvId TEXT NOT NULL, collectedAt TEXT NOT NULL, viewCount INTEGER, danmakuCount INTEGER, replyCount INTEGER, favoriteCount INTEGER, coinCount INTEGER, shareCount INTEGER, likeCount INTEGER, sourceUrl TEXT, fetchStatus TEXT NOT NULL, errorMessage TEXT, captureSource TEXT NOT NULL DEFAULT 'UNKNOWN')")
                db.execSQL("CREATE INDEX index_video_snapshots_bvId_collectedAt ON video_snapshots (bvId, collectedAt)")
                db.execSQL("CREATE TABLE app_logs (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, time TEXT NOT NULL, level TEXT NOT NULL, tag TEXT NOT NULL, message TEXT NOT NULL, detail TEXT)")
                db.execSQL("INSERT INTO videos VALUES ('BV1xx411c7mD',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
                db.execSQL("INSERT INTO video_snapshots (bvId,collectedAt,fetchStatus,captureSource) VALUES ('BV1xx411c7mD','2026-01-01T00:00:00Z','success','UNKNOWN')")
            }
            override fun onUpgrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
        }).build()
        FrameworkSQLiteOpenHelperFactory().create(config).writableDatabase.close()

        val database = Room.databaseBuilder(context, AppDatabase::class.java, name)
            .addMigrations(AppDatabase.MIGRATION_2_3, AppDatabase.MIGRATION_3_4)
            .build()
        val cursor = database.openHelper.readableDatabase.query("SELECT captureSource, exchangeDigest, collectedAtEpochMillis FROM video_snapshots")
        cursor.moveToFirst()
        assertEquals("UNKNOWN", cursor.getString(0))
        assertEquals(true, cursor.isNull(1))
        assertEquals(1767225600000L, cursor.getLong(2))
        cursor.close()
        val videoCursor = database.openHelper.readableDatabase.query("SELECT coverUrl FROM videos")
        videoCursor.moveToFirst()
        assertEquals(true, videoCursor.isNull(0))
        videoCursor.close()
        database.close()
    }
}
