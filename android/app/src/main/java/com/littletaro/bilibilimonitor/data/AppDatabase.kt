package com.littletaro.bilibilimonitor.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [VideoEntity::class, VideoSnapshotEntity::class, AppLogEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun dao(): MonitorDao

    companion object {
        fun create(context: Context): AppDatabase =
            Room.databaseBuilder(context, AppDatabase::class.java, "bilibili_monitor.db")
                .fallbackToDestructiveMigration()
                .build()
    }
}
