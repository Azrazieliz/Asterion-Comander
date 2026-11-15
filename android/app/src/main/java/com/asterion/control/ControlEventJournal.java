package com.asterion.control;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.os.SystemClock;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicInteger;

/** Durable, bounded, owner-private local diagnostics; NEVER captures user content.
 * No global Logcat and no privileged access to other applications.
 */
final class ControlEventJournal extends SQLiteOpenHelper {
  private static final String DATABASE="control_diagnostics_v1.sqlite3";
  private static final int MAX_EVENTS=5000;
  private static final AtomicInteger WRITES=new AtomicInteger();
  private static volatile ControlEventJournal singleton;

  private ControlEventJournal(Context context){
    super(context.getApplicationContext(), DATABASE,null,1);
    setWriteAheadLoggingEnabled(true);
  }
  static ControlEventJournal get(Context context){
    ControlEventJournal result=singleton;
    if(result==null)synchronized(ControlEventJournal.class){
      result=singleton;
      if(result==null)singleton=result=new ControlEventJournal(context);
    }
    return result;
  }
  @Override public void onCreate(SQLiteDatabase db){
    db.execSQL("CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,"+
      "utc_ms INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL,"+
      "kind TEXT NOT NULL, stage TEXT NOT NULL, state TEXT NOT NULL,"+
      "reason_code TEXT NOT NULL, duration_ms INTEGER NOT NULL)");
    db.execSQL("CREATE INDEX idx_diagnostic_time ON events(utc_ms)");
  }
  @Override public void onUpgrade(SQLiteDatabase db,int previous,int current){
    // On future migrations preserve existing incident history.
    throw new IllegalStateException("No automatic destructive diagnostic migration");
  }
  private static String safe(String value){
    if(value==null)return "unspecified";
    String v=value.trim().toLowerCase(Locale.ROOT);
    if(v.length()<1||v.length()>80||!v.matches("[a-z0-9_.:-]+"))
      return "redacted_non_identifier";
    if(v.contains("secret")||v.contains("token")||v.contains("password")||
       v.contains("cookie")||v.contains("credential")||v.contains("bearer"))
      return "redacted_non_identifier";
    return v;
  }
  static void write(Context context,String kind,String stage,String state,
                    String reasonCode,long durationMs){
    // Instrumentation MUST NOT make a healthy remote-control operation fail.
    try {
      ControlEventJournal journal=get(context);
      synchronized(journal){
        SQLiteDatabase db=journal.getWritableDatabase();
        android.content.ContentValues row=new android.content.ContentValues();
        row.put("utc_ms",System.currentTimeMillis());
        row.put("elapsed_ms",SystemClock.elapsedRealtime());
        row.put("kind",safe(kind));
        row.put("stage",safe(stage));
        row.put("state",safe(state));
        row.put("reason_code",safe(reasonCode));
        row.put("duration_ms",Math.max(0,Math.min(3600000L,durationMs)));
        db.insertOrThrow("events",null,row);
        if(WRITES.incrementAndGet()%100==0){
          db.execSQL("DELETE FROM events WHERE seq NOT IN "+
            "(SELECT seq FROM events ORDER BY seq DESC LIMIT "+MAX_EVENTS+")");
        }
      }
    } catch(Exception ignored){}
  }
  static JSONObject recent(Context context,long since,int limit)throws Exception{
    if(since<0||limit<1||limit>200)throw new IllegalArgumentException("Invalid cursor or limit");
    ControlEventJournal journal=get(context);
    JSONArray rows=new JSONArray();
    long next=since,oldest=0,latest=0;
    synchronized(journal){
      SQLiteDatabase db=journal.getReadableDatabase();
      try(Cursor bounds=db.rawQuery(
          "SELECT COALESCE(MIN(seq),0), COALESCE(MAX(seq),0) FROM events",null)){
        if(bounds.moveToFirst()){oldest=bounds.getLong(0);latest=bounds.getLong(1);}
      }
      try(Cursor cur=db.rawQuery(
          "SELECT seq,utc_ms,elapsed_ms,kind,stage,state,reason_code,duration_ms "+
          "FROM events WHERE seq>? ORDER BY seq ASC LIMIT ?",
          new String[]{Long.toString(since),Integer.toString(limit)})){
        while(cur.moveToNext()){
          long seq=cur.getLong(0);
          rows.put(new JSONObject().put("seq",seq).put("utc_ms",cur.getLong(1))
            .put("elapsed_ms",cur.getLong(2)).put("kind",cur.getString(3))
            .put("stage",cur.getString(4)).put("state",cur.getString(5))
            .put("reason_code",cur.getString(6))
            .put("duration_ms",cur.getLong(7)));
          next=seq;
        }
      }
    }
    return new JSONObject().put("ok",true).put("scope","asterion_control_process_only")
      .put("schema_version",1).put("events",rows).put("next_sequence",next)
      .put("oldest_sequence",oldest).put("latest_sequence",latest)
      .put("dropped_before_cursor",since>0 && oldest>since+1 ? oldest-since-1 : 0)
      .put("retained_event_limit",MAX_EVENTS);
  }
}
