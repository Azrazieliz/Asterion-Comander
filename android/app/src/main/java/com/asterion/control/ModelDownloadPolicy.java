package com.asterion.control;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Pure-JVM trusted-download policy for owner-selected offline GGUF models.
 * No Android/Gradle dependency; can be compiled and regression-tested without
 * changing the installed app, original signing key or downloading weights.
 *
 * A model selected through public Hugging Face metadata MUST have an immutable
 * revision commit, SHA-256 of actual weight bytes and checked expected size.
 * The policy authorizes source URLs on huggingface.co and the documented HF
 * CDN domains (*.hf.co); arbitrary redirects to other hosts are forbidden.
 */
final class ModelDownloadPolicy {
  private ModelDownloadPolicy(){}

  static final long MIN_MODEL_BYTES=100_000_000L;
  static final long MAX_MODEL_BYTES=8_000_000_000L;
  static final String DEFAULT_REPOSITORY="bartowski/Qwen_Qwen3.5-2B-GGUF";
  static final String DEFAULT_FILENAME="Qwen_Qwen3.5-2B-Q4_K_M.gguf";
  private static final Pattern COMMIT=Pattern.compile("[0-9a-f]{40}");
  private static final Pattern SHA=Pattern.compile("[0-9a-f]{64}");
  private static final Pattern REPO=Pattern.compile(
      "[A-Za-z0-9][A-Za-z0-9_.-]{1,90}/[A-Za-z0-9][A-Za-z0-9_.-]{1,110}");
  private static final Pattern FILE=Pattern.compile(
      "[A-Za-z0-9][A-Za-z0-9_.-]{2,160}\\.gguf");

  static final class Manifest {
    final String repository, revision, filename, sha256, license;
    final long sizeBytes;
    Manifest(String repository,String revision,String filename,
             String sha256,long sizeBytes,String license){
      if(repository==null||!REPO.matcher(repository).matches()||
         filename==null||!FILE.matcher(filename).matches()||
         revision==null||!COMMIT.matcher(revision).matches()||
         sha256==null||!SHA.matcher(sha256).matches()||
         sizeBytes<MIN_MODEL_BYTES||sizeBytes>MAX_MODEL_BYTES||
         !"apache-2.0".equalsIgnoreCase(license))
        throw new IllegalArgumentException("Unverified GGUF artifact manifest");
      this.repository=repository;
      this.revision=revision;
      this.filename=filename;
      this.sha256=sha256;
      this.sizeBytes=sizeBytes;
      this.license=license.toLowerCase(Locale.ROOT);
    }
    URL downloadUrl()throws Exception{
      return new URI("https", "huggingface.co",
          "/"+repository+"/resolve/"+revision+"/"+filename,
          null).toURL();
    }
    String privateFilename(){
      return sha256.substring(0,18)+"-"+filename;
    }
  }

  static boolean trustedArtifactUrl(URL url,boolean firstRequest){
    try{
      if(url==null||!"https".equalsIgnoreCase(url.getProtocol())||
         url.getPort()!=-1&&url.getPort()!=443||
         url.toURI().getUserInfo()!=null||url.getRef()!=null)return false;
      String host=url.getHost().toLowerCase(Locale.ROOT);
      if(firstRequest)return "huggingface.co".equals(host);
      return "huggingface.co".equals(host)||
             host.endsWith(".hf.co")&&!host.equals(".hf.co");
    }catch(Exception e){return false;}
  }

  static String normalizeHashHeader(String value){
    if(value==null)return "";
    String clean=value.trim();
    if(clean.startsWith("\"")&&clean.endsWith("\"")&&clean.length()==66)
      clean=clean.substring(1,65);
    clean=clean.toLowerCase(Locale.ROOT);
    return SHA.matcher(clean).matches()?clean:"";
  }

  static long sizeHeader(String value){
    if(value==null||value.isEmpty()||value.length()>20)return -1L;
    for(int i=0;i<value.length();i++)
      if(value.charAt(i)<'0'||value.charAt(i)>'9')return -1L;
    try{
      long n=Long.parseLong(value);
      return n>=MIN_MODEL_BYTES&&n<=MAX_MODEL_BYTES?n:-1L;
    }catch(NumberFormatException e){return -1L;}
  }

  static boolean realGgufMagic(File source)throws IOException{
    if(source==null||!source.isFile()||source.length()<4)return false;
    try(FileInputStream input=new FileInputStream(source)){
      return input.read()=='G'&&input.read()=='G'&&
             input.read()=='U'&&input.read()=='F';
    }
  }

  static String digest(File source)throws Exception{
    MessageDigest hash=MessageDigest.getInstance("SHA-256");
    try(FileInputStream input=new FileInputStream(source)){
      byte[] chunk=new byte[512*1024];
      for(int count;(count=input.read(chunk))!=-1;)
        hash.update(chunk,0,count);
    }
    StringBuilder hex=new StringBuilder(64);
    for(byte b:hash.digest())
      hex.append(String.format(Locale.ROOT,"%02x",b&0xff));
    return hex.toString();
  }

  static boolean verifiedFile(File file,Manifest manifest)throws Exception{
    return file!=null&&file.isFile()&&file.length()==manifest.sizeBytes&&
           realGgufMagic(file)&&digest(file).equals(manifest.sha256);
  }

  static long freeSpaceRequired(long bytes){
    if(bytes<MIN_MODEL_BYTES||bytes>MAX_MODEL_BYTES)
      throw new IllegalArgumentException("Invalid weight file size");
    // Two copies allow safe staging and rollback. Model loading also needs
    // separate free RAM; storage size alone is NOT a load permit.
    return Math.addExact(Math.multiplyExact(bytes,2L),512_000_000L);
  }
}
