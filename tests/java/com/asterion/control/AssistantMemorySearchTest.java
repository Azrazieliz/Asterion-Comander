package com.asterion.control;
public final class AssistantMemorySearchTest {
    private static void require(boolean value,String name){if(!value)throw new AssertionError(name);}
    public static void main(String[] args){
        AssistantMemorySearch s=new AssistantMemorySearch("Find the rare orchid configuration");
        for(int i=0;i<4095;i++)s.add("recent-"+i,"General","note","routine information "+i,100+i,false);
        s.add("old","Asterion","owner decision","rare orchid configuration",1,true);
        require(s.render().contains("Memory ID: old"),"old match");
        AssistantMemorySearch longText=new AssistantMemorySearch("saffron telescope");
        String prefix="irrelevant ".repeat(600);
        String content=prefix+"saffron telescope 🌱 source passage";
        longText.add("long","Asterion","spec",content,1,true);
        String result=longText.render();
        require(result.contains("Exact excerpt UTF-16"),"excerpt label");
        require(result.contains("saffron telescope"),"late passage");
        require(result.contains("Memory ID: long"),"source id");
        require(result.length()<=4500,"bounded output");
        AssistantMemorySearch noTerms=new AssistantMemorySearch("the and please");
        require(noTerms.empty(),"stop words");
        AssistantMemorySearch ranked=new AssistantMemorySearch("database encryption");
        ranked.add("recent","General","note","database",100,false);
        ranked.add("specific","Project","note","database encryption",1,true);
        require(ranked.render().indexOf("specific")<ranked.render().indexOf("recent"),"relevance before recency");
        System.out.println("Memory search behavior passed");
    }
}
