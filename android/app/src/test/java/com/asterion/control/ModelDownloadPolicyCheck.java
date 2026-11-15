package com.asterion.control;

import java.io.File;
import java.io.FileOutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/**
 * JDK-only real parser/download policy regression; no network/download,
 * no Android classes, no application APK build or signing.
 */
public final class ModelDownloadPolicyCheck {
  private static int cases=0;
  private static void yes(boolean check,String message){
    cases++;
    if(!check)throw new AssertionError(message);
  }
  private static void forbidden(Runnable action){
    cases++;
    try{action.run();}
    catch(IllegalArgumentException expected){return;}
    throw new AssertionError("Expected rejection");
  }
  public static void main(String[] ignored)throws Exception{
    String sha="a".repeat(64);
    String commit="b".repeat(40);
    ModelDownloadPolicy.Manifest model=new ModelDownloadPolicy.Manifest(
      "bartowski/Qwen_Qwen3.5-2B-GGUF",commit,
      "Qwen_Qwen3.5-2B-Q4_K_M.gguf",sha,1_400_000_000L,"apache-2.0");
    yes(model.downloadUrl().toString().contains("/resolve/"+commit+"/"),
        "Pinned immutable revision");
    yes(model.privateFilename().startsWith("a".repeat(18)+"-"),
        "SHA-derived isolated filename");
    yes(ModelDownloadPolicy.trustedArtifactUrl(model.downloadUrl(),true),
        "Official Hugging Face source");
    for(String url:new String[]{
        "https://huggingface.co/safe",
        "https://cas-bridge.xethub.hf.co/a",
        "https://transfer.xethub.hf.co/b",
        "https://cdn-lfs-us-1.hf.co/c",
        "https://cas-server.xethub-eu.hf.co/d",
        "https://us.aws.cdn.hf.co/signed"})
      yes(ModelDownloadPolicy.trustedArtifactUrl(new URL(url),false),
          "Trusted HF CDN "+url);
    for(String url:new String[]{
        "http://huggingface.co/file",
        "https://huggingface.co.evil.com/file",
        "https://hf.co.evil.com/steal",
        "https://bad-hf.co.invalid/file",
        "https://example.com/model.gguf",
        "https://huggingface.co:4443/unsafe",
        "https://user:token@huggingface.co/private"})
      yes(!ModelDownloadPolicy.trustedArtifactUrl(new URL(url),false),
          "Reject insecure redirect "+url);
    yes(!ModelDownloadPolicy.trustedArtifactUrl(
        new URL("https://us.aws.cdn.hf.co/signed"),true),
        "CDN not initial Hub source");
    yes(sha.equals(ModelDownloadPolicy.normalizeHashHeader("\""+sha+"\"")),
        "Quoted LFS SHA256");
    yes(sha.equals(ModelDownloadPolicy.normalizeHashHeader(sha)),
        "Bare SHA256");
    yes("".equals(ModelDownloadPolicy.normalizeHashHeader("abc")),
        "Invalid hash rejected");
    yes(1_400_000_000L==ModelDownloadPolicy.sizeHeader("1400000000"),
        "Signed model size");
    yes(-1==ModelDownloadPolicy.sizeHeader("-50"),
        "Negative size rejected");
    yes(-1==ModelDownloadPolicy.sizeHeader("9999999999999999999999"),
        "Overflow size rejected");
    forbidden(()->new ModelDownloadPolicy.Manifest(
        "../evil/dir",commit,"model.gguf",sha,1_400_000_000L,"apache-2.0"));
    forbidden(()->new ModelDownloadPolicy.Manifest(
        "bartowski/Qwen_Qwen3.5-2B-GGUF","main",
        "model.gguf",sha,1_400_000_000L,"apache-2.0"));
    forbidden(()->new ModelDownloadPolicy.Manifest(
        "bartowski/Qwen_Qwen3.5-2B-GGUF",commit,
        "../model.gguf",sha,1_400_000_000L,"apache-2.0"));
    forbidden(()->new ModelDownloadPolicy.Manifest(
        "bartowski/Qwen_Qwen3.5-2B-GGUF",commit,
        "model.gguf",sha,1_400_000_000L,"restricted-unreviewed"));
    yes(ModelDownloadPolicy.freeSpaceRequired(1_400_000_000L)==
        3_312_000_000L,"Staged+rollback disk allowance");
    File file=File.createTempFile("asterion-gguf-policy",".gguf");
    try{
      byte[] payload="GGUFtest".getBytes(StandardCharsets.US_ASCII);
      try(FileOutputStream output=new FileOutputStream(file)){
        output.write(payload);
      }
      yes(ModelDownloadPolicy.realGgufMagic(file),
          "Real GGUF magic bytes");
      yes(ModelDownloadPolicy.digest(file).length()==64,
          "SHA256 actually computed from file bytes");
      yes(!ModelDownloadPolicy.verifiedFile(file,model),
          "Wrong hash/size must not be approved");
      try(FileOutputStream output=new FileOutputStream(file)){
        output.write("fake".getBytes(StandardCharsets.US_ASCII));
      }
      yes(!ModelDownloadPolicy.realGgufMagic(file),
          "Malformed GGUF not considered actual weights");
    }finally{file.delete();}
    System.out.println("MODEL_DOWNLOAD_POLICY_JAVA_CHECKS "+cases+" PASS");
  }
}
