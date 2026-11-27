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
    private static final int MAX_RECORDS=4096;
    private ControlAssistantMemory(){}

    private static final class Database extends SQLiteOpenHelper {
        Database(Context c){super(c,DB,null,2);}
        @Override public void onCreate(SQLiteDatabase db){
            db.execSQL("CREATE TABLE IF NOT EXISTS memory("+
                "id TEXT PRIMARY KEY, project TEXT NOT NULL, origin TEXT NOT NULL,"+
                "nonce BLOB NOT NULL, payload BLOB NOT NULL, created_ms INTEGER NOT NULL)");
            db.execSQL("CREATE INDEX IF NOT EXISTS memory_recent ON memory(created_ms DESC)");
            createConversations(db);
        }
        @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion){
            if(oldVersion==1&&newVersion==2){createConversations(db);return;}
            throw new IllegalStateException("memory_schema_requires_migration");
        }
    }
    private static void createConversations(SQLiteDatabase db){
        db.execSQL("CREATE TABLE IF NOT EXISTS conversation("+
            "id TEXT PRIMARY KEY, nonce BLOB NOT NULL, payload BLOB NOT NULL, updated_ms INTEGER NOT NULL)");
        db.execSQL("CREATE INDEX IF NOT EXISTS conversation_recent ON conversation(updated_ms DESC)");
    }
    static void saveConversation(Context context,AssistantConversation conversation)throws Exception{
        if(!ControlAssistantPreferences.saveHistory(context))return;
        synchronized(LOCK){
            JSONArray messages=new JSONArray();
            for(AssistantConversation.Message m:conversation.messages){
                JSONObject entry=new JSONObject().put("id",m.id).put("role",m.role).put("text",m.text).put("state",m.state)
                    .put("omitted_context_messages",m.omittedContextMessages).put("omitted_reference_blocks",m.omittedReferenceBlocks);
                AssistantActionRecord record=m.actionRecord;
                if(record!=null)entry.put("action_receipt",new JSONObject().put("id",record.requestId)
                    .put("package",record.appPackage).put("action",record.action)
                    .put("submission",record.submission).put("observation",record.observation));
                messages.put(entry);
            }
            byte[] plain=new JSONObject().put("title",conversation.title).put("project",conversation.project)
                .put("messages",messages).toString().getBytes(StandardCharsets.UTF_8);
            if(plain.length>1_000_000)throw new IllegalStateException("conversation_storage_budget_exceeded");
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE,key());
            cipher.updateAAD(conversation.id.getBytes(StandardCharsets.UTF_8));
            ContentValues row=new ContentValues();row.put("id",conversation.id);
            row.put("nonce",cipher.getIV());row.put("payload",cipher.doFinal(plain));
            row.put("updated_ms",System.currentTimeMillis());
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getWritableDatabase()){
                if(db.insertWithOnConflict("conversation",null,row,SQLiteDatabase.CONFLICT_REPLACE)<0)
                    throw new IllegalStateException("conversation_not_saved");
            }finally{helper.close();}
        }
    }
    static AssistantConversation loadConversation(Context context,String id)throws Exception{
        synchronized(LOCK){
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getReadableDatabase();Cursor cursor=db.rawQuery(
                "SELECT nonce,payload FROM conversation WHERE id=?",new String[]{id})){
                if(!cursor.moveToFirst())throw new IllegalArgumentException("conversation_missing");
                Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,cursor.getBlob(0)));
                cipher.updateAAD(id.getBytes(StandardCharsets.UTF_8));
                JSONObject saved=new JSONObject(new String(cipher.doFinal(cursor.getBlob(1)),StandardCharsets.UTF_8));
                AssistantConversation out=new AssistantConversation(id);
                out.title=saved.getString("title");out.project=saved.getString("project");
                JSONArray messages=saved.getJSONArray("messages");
                for(int i=0;i<messages.length();i++){
                    JSONObject m=messages.getJSONObject(i);
                    out.messages.add(new AssistantConversation.Message(m.getString("id"),m.getString("role"),
                        m.getString("text"),m.getString("state")));
                    out.messages.get(out.messages.size()-1).omittedContextMessages=m.optInt("omitted_context_messages",0);
                    out.messages.get(out.messages.size()-1).omittedReferenceBlocks=m.optInt("omitted_reference_blocks",0);
                    JSONObject receipt=m.optJSONObject("action_receipt");
                    if(receipt!=null)out.messages.get(out.messages.size()-1).actionRecord=new AssistantActionRecord(
                        receipt.getString("id"),receipt.getString("package"),receipt.getString("action"),
                        receipt.getString("submission"),receipt.getString("observation"));
                }
                out.recover();return out;
            }finally{helper.close();}
        }
    }
    static JSONArray conversations(Context context)throws Exception{
        synchronized(LOCK){
            ArrayList<String> ids=new ArrayList<>();
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getReadableDatabase();Cursor c=db.rawQuery(
                "SELECT id FROM conversation ORDER BY updated_ms DESC LIMIT 100",null)){
                while(c.moveToNext())ids.add(c.getString(0));
            }finally{helper.close();}
            JSONArray result=new JSONArray();
            for(String id:ids){AssistantConversation c=loadConversation(context,id);
                result.put(new JSONObject().put("id",id).put("title",c.title).put("project",c.project));}
            return result;
        }
    }
    static boolean deleteConversation(Context context,String id){
        synchronized(LOCK){
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getWritableDatabase()){
                return db.delete("conversation","id=?",new String[]{id})==1;
            }finally{helper.close();}
        }
    }
    // Local scheduled tasks use the same private memory key but independent AAD.
    // The entire bounded task collection is sealed before any background dispatch.
    private static final String SCHEDULE_PREFS="control_assistant_schedules_v1";
    private static final byte[] SCHEDULE_AAD="Asterion.Control.Schedules.v1".getBytes(StandardCharsets.UTF_8);
    static JSONArray loadSchedules(Context c)throws Exception{
        synchronized(LOCK){
            String sealed=c.getSharedPreferences(SCHEDULE_PREFS,Context.MODE_PRIVATE).getString("sealed",null);
            if(sealed==null)return new JSONArray();
            if(sealed.length()>2_000_000)throw new IllegalStateException("schedule_storage_budget");
            byte[] bytes=android.util.Base64.decode(sealed,android.util.Base64.NO_WRAP);
            if(bytes.length<28)throw new IllegalStateException("invalid_schedule_ciphertext");
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,java.util.Arrays.copyOf(bytes,12)));
            cipher.updateAAD(SCHEDULE_AAD);
            return new JSONArray(new String(cipher.doFinal(bytes,12,bytes.length-12),StandardCharsets.UTF_8));
        }
    }
    static void saveSchedules(Context c,JSONArray rows)throws Exception{
        synchronized(LOCK){
            byte[] plain=rows.toString().getBytes(StandardCharsets.UTF_8);
            if(rows.length()>32||plain.length>1_000_000)throw new IllegalStateException("schedule_storage_budget");
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE,key());
            cipher.updateAAD(SCHEDULE_AAD);
            byte[] nonce=cipher.getIV(),payload=cipher.doFinal(plain);
            if(nonce.length!=12)throw new IllegalStateException("unexpected_schedule_nonce");
            byte[] sealed=new byte[nonce.length+payload.length];
            System.arraycopy(nonce,0,sealed,0,nonce.length);
            System.arraycopy(payload,0,sealed,nonce.length,payload.length);
            String encoded=android.util.Base64.encodeToString(sealed,android.util.Base64.NO_WRAP);
            if(!c.getSharedPreferences(SCHEDULE_PREFS,Context.MODE_PRIVATE).edit().putString("sealed",encoded).commit())
                throw new IllegalStateException("schedule_receipt_not_persisted");
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
    static String relevant(Context context,String query)throws Exception{return relevant(context,query,"General");}
    static String relevant(Context context,String query,String selectedProject)throws Exception{
        if(query==null||query.isBlank())return "";
        AssistantMemorySearch search=new AssistantMemorySearch(query);
        if(search.empty())return "";
        synchronized(LOCK){
            SecretKey secret=key();
            Database helper=new Database(context.getApplicationContext());
            try(SQLiteDatabase db=helper.getReadableDatabase();
                Cursor cursor=db.rawQuery(
                    "SELECT id,project,origin,nonce,payload,created_ms FROM memory "+
                    "WHERE (project=? OR project='General') ORDER BY created_ms DESC",new String[]{selectedProject})){
                int scanned=0;
                while(cursor.moveToNext()){
                    if(++scanned>MAX_RECORDS)throw new IllegalStateException("memory_record_budget_exceeded");
                    String content=decrypt(secret,cursor.getBlob(3),cursor.getBlob(4));
                    String project=cursor.getString(1);
                    search.add(cursor.getString(0),project,cursor.getString(2),content,
                        cursor.getLong(5),project.equals(selectedProject));
                }
            }finally{helper.close();}
        }
        return search.render();
    }
}
