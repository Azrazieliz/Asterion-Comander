package com.asterion.control;
public final class ProjectSourceTextTest {
    static void check(boolean yes){if(!yes)throw new AssertionError();}
    public static void main(String[] args)throws Exception{
        String raw="x".repeat(7999)+"🌱"+"y".repeat(9000)+" rare orchid at the end";
        ProjectSourceText source=new ProjectSourceText("notes.txt",raw.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        int end=0;
        StringBuilder rebuilt=new StringBuilder();
        for(ProjectSourceText.Passage p:source.passages()){
            check(p.start<=end&&p.end>end);
            check(p.text.equals(raw.substring(p.start,p.end)));
            check(!Character.isLowSurrogate(p.text.charAt(0)));
            check(!Character.isHighSurrogate(p.text.charAt(p.text.length()-1)));
            rebuilt.append(raw,end,p.end);end=p.end;
        }
        check(rebuilt.toString().equals(raw));check(source.digest.length()==64);
        try{new ProjectSourceText("bad",new byte[]{(byte)0xff});throw new AssertionError();}
        catch(java.nio.charset.CharacterCodingException expected){}
        try{new ProjectSourceText("bad",new byte[]{0,1,2});throw new AssertionError();}
        catch(IllegalArgumentException expected){}
        try{new ProjectSourceText("large",new byte[ProjectSourceText.MAX_BYTES+1]);throw new AssertionError();}
        catch(IllegalArgumentException expected){}
        System.out.println("Exact project source chunks passed");
    }
}
