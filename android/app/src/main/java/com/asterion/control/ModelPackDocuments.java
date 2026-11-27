package com.asterion.control;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;

/** One signed model may arrive as a full document or bounded transfer parts.
 * Parts are concatenated lazily, then the existing loader verifies the entire
 * signed SHA-256 and length before atomic publication. No path is inferred
 * from a provider filename and no new transfer protocol is introduced. */
final class ModelPackDocuments {
    private ModelPackDocuments(){}
    private static InputStream open(Context context,Uri uri)throws IOException{
        InputStream input=context.getContentResolver().openInputStream(uri);
        if(input==null)throw new IOException("model_document_unavailable");
        return input;
    }
    static InputStream open(Context context,List<Uri> selected,String expectedName)throws IOException{
        if(selected==null||selected.isEmpty()||selected.size()>32)
            throw new IllegalArgumentException("invalid_model_part_count");
        for(Uri uri:selected)if(uri==null||!"content".equals(uri.getScheme()))
            throw new SecurityException("document_provider_required");
        if(new java.util.HashSet<>(selected).size()!=selected.size())
            throw new IllegalArgumentException("duplicate_model_document");
        if(selected.size()==1)return open(context,selected.get(0));
        TreeMap<Integer,Uri> sorted=new TreeMap<>();
        String prefix=expectedName+".part";
        for(Uri uri:selected){
            String name=null;
            try(Cursor c=context.getContentResolver().query(uri,
                    new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                if(c!=null&&c.moveToFirst())name=c.getString(0);
            }
            if(name==null||!name.startsWith(prefix)||!name.substring(prefix.length()).matches("[0-9]{4}"))
                throw new IllegalArgumentException("unexpected_model_part_name");
            int index=Integer.parseInt(name.substring(prefix.length()));
            if(index<1||index>selected.size()||sorted.put(index,uri)!=null)
                throw new IllegalArgumentException("invalid_model_part_order");
        }
        List<Uri> ordered=new ArrayList<>(sorted.values());
        return new InputStream(){
            int index=0;
            InputStream current;
            boolean closed;
            private boolean next()throws IOException{
                if(closed)throw new IOException("model_stream_closed");
                if(current!=null)return true;
                if(index>=ordered.size())return false;
                current=open(context,ordered.get(index++));return true;
            }
            @Override public int read(byte[] b,int off,int len)throws IOException{
                if(len==0)return 0;
                while(next()){
                    int n=current.read(b,off,len);
                    if(n>=0)return n;
                    current.close();current=null;
                }
                return -1;
            }
            @Override public int read()throws IOException{
                byte[] one=new byte[1];int n=read(one,0,1);return n<0?-1:one[0]&255;
            }
            @Override public void close()throws IOException{
                closed=true;
                if(current!=null){try{current.close();}finally{current=null;}}
            }
        };
    }
}
