package com.asterion.control;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.net.Uri;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.Arrays;

final class OnDeviceVisionImage implements AutoCloseable {
    final int width,height;
    final byte[] rgb;
    final String sha256;
    private OnDeviceVisionImage(int w,int h,byte[] rgb)throws Exception{
        this.width=w;this.height=h;this.rgb=rgb;
        MessageDigest hash=MessageDigest.getInstance("SHA-256");
        hash.update(ByteBuffer.allocate(8).putInt(w).putInt(h).array());
        sha256=java.util.HexFormat.of().formatHex(hash.digest(rgb));
    }
    static OnDeviceVisionImage read(Context c,Uri uri,int maxSide,InferenceGate.Request request)throws Exception{
        if(uri==null||!"content".equals(uri.getScheme()))throw new SecurityException("document_provider_required");
        if(request.isCancelled())throw new InterruptedException("user_cancelled");
        byte[] source;
        try(InputStream input=c.getContentResolver().openInputStream(uri)){
            if(input==null)throw new java.io.IOException("no_image_stream");
            source=input.readNBytes((32<<20)+1);
        }
        Bitmap bitmap=null;
        try{
            if(source.length==0||source.length>(32<<20))throw new IllegalArgumentException("image_input_budget");
            if(request.isCancelled())throw new InterruptedException("user_cancelled");
            bitmap=ImageDecoder.decodeBitmap(ImageDecoder.createSource(ByteBuffer.wrap(source)),(decoder,info,src)->{
                int w=info.getSize().getWidth(),h=info.getSize().getHeight();
                if(w<1||h<1||(long)w*h>64000000L)throw new IllegalArgumentException("image_dimension_budget");
                if(info.isAnimated())throw new IllegalArgumentException("animated_image_requires_frame_selection");
                double scale=Math.min(1.0,(double)maxSide/Math.max(w,h));
                decoder.setTargetSize(Math.max(1,(int)Math.round(w*scale)),Math.max(1,(int)Math.round(h*scale)));
                decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);
                decoder.setTargetColorSpace(android.graphics.ColorSpace.get(android.graphics.ColorSpace.Named.SRGB));
                decoder.setOnPartialImageListener(error->false);
            });
            int w=bitmap.getWidth(),h=bitmap.getHeight();
            if(w<1||h<1||w>maxSide||h>maxSide)throw new IllegalStateException("decoded_image_budget");
            int[] row=new int[w];byte[] rgb=new byte[w*h*3];boolean complete=false;
            try{
                for(int y=0;y<h;y++){
                    if(request.isCancelled())throw new InterruptedException("user_cancelled");
                    bitmap.getPixels(row,0,w,0,y,w,1);
                    for(int x=0;x<w;x++){
                        int p=row[x],a=p>>>24,at=(y*w+x)*3;
                        rgb[at]=(byte)((((p>>>16)&255)*a+255*(255-a)+127)/255);
                        rgb[at+1]=(byte)((((p>>>8)&255)*a+255*(255-a)+127)/255);
                        rgb[at+2]=(byte)(((p&255)*a+255*(255-a)+127)/255);
                    }
                }
                OnDeviceVisionImage image=new OnDeviceVisionImage(w,h,rgb);complete=true;return image;
            }finally{Arrays.fill(row,0);if(!complete)Arrays.fill(rgb,(byte)0);}
        }finally{Arrays.fill(source,(byte)0);if(bitmap!=null)bitmap.recycle();}
    }
    @Override public void close(){Arrays.fill(rgb,(byte)0);}
}
