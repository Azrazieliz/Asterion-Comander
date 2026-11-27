package com.asterion.control;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/** Real bounded UTF-8 artifact, never an executable action. Office/media formats
 * stay with their owning specialist engines; this is only native text export.
 */
final class AssistantArtifact {
    final String filename,mime;
    private final byte[] bytes;
    private AssistantArtifact(String filename,String mime,byte[] bytes){this.filename=filename;this.mime=mime;this.bytes=bytes;}
    static AssistantArtifact create(String language,String content){
        String ext,mime;
        switch(language.toLowerCase(Locale.ROOT)){
            case "":case "text":case "txt":ext="txt";mime="text/plain";break;
            case "markdown":case "md":ext="md";mime="text/markdown";break;
            case "json":ext="json";mime="application/json";break;
            case "csv":ext="csv";mime="text/csv";break;
            case "tsv":ext="tsv";mime="text/tab-separated-values";break;
            case "xml":ext="xml";mime="application/xml";break;
            case "yaml":case "yml":ext="yaml";mime="text/plain";break;
            case "html":ext="html";mime="text/html";break;
            case "css":ext="css";mime="text/css";break;
            case "js":case "javascript":ext="js";mime="text/plain";break;
            case "ts":case "typescript":ext="ts";mime="text/plain";break;
            case "py":case "python":ext="py";mime="text/plain";break;
            case "java":ext="java";mime="text/plain";break;
            case "cpp":case "c++":ext="cpp";mime="text/plain";break;
            case "c":ext="c";mime="text/plain";break;
            case "kotlin":case "kt":ext="kt";mime="text/plain";break;
            case "sql":ext="sql";mime="text/plain";break;
            default:return null;
        }
        byte[] bytes=content.getBytes(StandardCharsets.UTF_8);
        if(bytes.length==0||bytes.length>262144)return null;
        return new AssistantArtifact("asterion."+ext,mime,bytes);
    }
    byte[] data(){return bytes.clone();}
    int size(){return bytes.length;}
    boolean verified(byte[] actual){return actual!=null&&MessageDigest.isEqual(bytes,actual);}
}
