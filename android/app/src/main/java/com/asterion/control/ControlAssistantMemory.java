package com.asterion.control;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Control-owned encrypted, explicitly saved assistant memories.
 * AES-256-GCM key is AndroidKeyStore-bound; no plaintext memory or passwords
 * go into bridge, GitHub or shared provider logs. Not Core/Nexus taxonomy.
 * Retrieval is intentionally lexical and bounded, not a claimed vector model.
 */
final class ControlAssistantMemory {
    private static final Object LOCK=new Object();
    private static final String KEY="asterion_control_ai_memory_aes_20261126";
    private static final String DB="asterion_control_ai_memories_v1.db";
    private static final int MAX_RECORDS=512;
    private ControlAssistantMemory(){}

    private static final class Database extends SQLiteOpenHelper {
        Database(Context c){super(c,DB,null,1);}
        @Override public void onCreate(SQLiteDatabase db){
            db.execSQL("CREATE TABLE IF NOT EXISTS memory("+
                "id TEXT PRIMARY KEY, project TEXT NOT NULL, origin TEXT NOT NULL,"+
                "nonce BLOB NOT NULL, payload BLOB NOT NULL, created_ms INTEGER NOT NULL)");
            db.execSQL("CREATE INDEX IF NOT EXISTS memory_recent ON memory(created_ms DESC)");
        }
        @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion){
            throw new IllegalStateException("memory_schema_requires_migration");
        }
    }
    private static SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        java.security.Key existing=store.getKey(KEY,null);
        if(existing instanceof SecretKey)return (SecretKey)existing;
        KeyGenerator generator=KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEY,
            KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).setRandomizedEncryptionRequired(true).build());
        return generator.generateKey();
    }
    private static String decrypt(SecretKey key,byte[] nonce,byte[] payload)throws Exception{
        if(nonce==null||nonce.length!=12||payload==null||payload.length<16)
            throw new IllegalStateException("invalid_encrypted_memory");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,nonce));
        return new String(cipher.doFinal(payload),StandardCharsets.UTF_8);
    }
    static String remember(Context context,String project,String source,String content,
                           boolean explicitlyOwnerApproved)throws Exception {
        if(!explicitlyOwnerApproved)throw new SecurityException("owner_memory_consent_required");
        if(project==null||!project.matches("[A-Za-z0-9_. -]{1,80}")||
                source==null||source.isBlank()||source.length()>120||
                content==null||content.isBlank()||content.length()>12000)
            throw new IllegalArgumentException("invalid_memory_payload");
        synchronized(LOCK){
            SecretKey secret=key();
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE,secret);
            byte[] nonce=cipher.getIV();
            byte[] payload=cipher.doFinal(content.getBytes(StandardCharsets.UTF_8));
            String id=UUID.randomUUID().toString();
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getWritableDatabase()){
                db.beginTransaction();
                try{
                    try(Cursor count=db.rawQuery("SELECT COUNT(*) FROM memory",null)){
                        if(count.moveToFirst()&&count.getInt(0)>=MAX_RECORDS)
                            throw new IllegalStateException("memory_limit_requires_owner_review");
                    }
                    ContentValues row=new ContentValues();
                    row.put("id",id);row.put("project",project);
                    row.put("origin",source);row.put("nonce",nonce);
                    row.put("payload",payload);row.put("created_ms",System.currentTimeMillis());
                    if(db.insertOrThrow("memory",null,row)<0)
                        throw new IllegalStateException("memory_not_saved");
                    db.setTransactionSuccessful();
                }finally{db.endTransaction();}
            }finally{helper.close();}
            return id;
        }
    }
    static JSONArray recent(Context context,int max)throws Exception {
        if(max<1||max>100)throw new IllegalArgumentException("invalid_memory_page");
        synchronized(LOCK){
            JSONArray rows=new JSONArray();
            SecretKey secret=key();
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getReadableDatabase();
                Cursor cursor=db.rawQuery(
                    "SELECT id,project,origin,nonce,payload,created_ms FROM memory "+
                    "ORDER BY created_ms DESC LIMIT "+max,null)){
                while(cursor.moveToNext()){
                    String plain=decrypt(secret,cursor.getBlob(3),cursor.getBlob(4));
                    rows.put(new JSONObject().put("id",cursor.getString(0))
                        .put("project",cursor.getString(1)).put("origin",cursor.getString(2))
                        .put("content",plain).put("created_ms",cursor.getLong(5)));
                }
            }finally{helper.close();}
            return rows;
        }
    }
    static boolean forget(Context context,String id,boolean explicitlyOwnerApproved){
        if(!explicitlyOwnerApproved)throw new SecurityException("owner_memory_consent_required");
        if(id==null||!id.matches("[0-9a-fA-F-]{36}"))
            throw new IllegalArgumentException("invalid_memory_id");
        synchronized(LOCK){
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getWritableDatabase()){
                return db.delete("memory","id=?",new String[]{id})==1;
            }finally{helper.close();}
        }
    }
    private static Set<String> terms(String value){
        Set<String> result=new HashSet<>();
        java.util.regex.Matcher m=java.util.regex.Pattern.compile(
            "[\\p{L}\\p{N}]{2,}").matcher(value.toLowerCase(Locale.ROOT));
        while(m.find()&&result.size()<90)result.add(m.group());
        return result;
    }
    private static final class Hit{
        final String id,project,source,content;
        final int score;
        Hit(String id,String project,String source,String content,int score){
            this.id=id;this.project=project;this.source=source;
            this.content=content;this.score=score;
        }
    }
    static String relevant(Context context,String query)throws Exception{
        if(query==null||query.isBlank())return "";
        Set<String> words=terms(query);
        if(words.isEmpty())return "";
        ArrayList<Hit> hits=new ArrayList<>();
        synchronized(LOCK){
            SecretKey secret=key();
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getReadableDatabase();
                Cursor cursor=db.rawQuery(
                    "SELECT id,project,origin,nonce,payload FROM memory "+
                    "ORDER BY created_ms DESC LIMIT 128",null)){
                while(cursor.moveToNext()){
                    String content=decrypt(secret,cursor.getBlob(3),cursor.getBlob(4));
                    String project=cursor.getString(1);
                    Set<String> indexed=terms(content+" "+project);
                    int score=0;
                    for(String word:words)if(indexed.contains(word))score++;
                    if(score>0)hits.add(new Hit(cursor.getString(0),project,
                        cursor.getString(2),content,score));
                }
            }finally{helper.close();}
        }
        hits.sort((a,b)->Integer.compare(b.score,a.score));
        StringBuilder out=new StringBuilder();
        int selected=0;
        for(Hit hit:hits){
            if(out.length()>=4000||selected>=5)break;
            String value="Project: "+hit.project+" | Evidence: "+hit.source+
                "\n"+hit.content+"\n---\n";
            if(out.length()+value.length()>4500)continue;
            out.append(value);
            selected++;
        }
        return out.toString();
    }
}
