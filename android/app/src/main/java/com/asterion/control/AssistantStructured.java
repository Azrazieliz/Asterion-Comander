package com.asterion.control;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;

/** Bounded, inert model response data. No script, URL, command or permission semantics. */
final class AssistantStructured {
    static final String CHART="asterion_chart", FORM="asterion_form";
    static final String GUIDANCE="For a useful visual use a fenced asterion_chart block: first line title|Chart title, then 1-12 lines bar|Label|nonnegative number. "+
        "For an interactive questionnaire use a fenced asterion_form block: first line title|Form title, then 1-8 lines question|Question|Option A|Option B (up to 6 options). "+
        "Use literal pipe separators, no pipes or newlines in labels. The owner selects answers and explicitly sends them as a new message. "+
        "For an editable text, JSON, CSV, Markdown or code file, provide a complete fenced code block with its language; the owner can save it. "+
        "Do not invent data, use components only when useful, and do not claim forms execute actions.";
    static final class Row {
        final String label,display;
        final double value;
        final List<String> options;
        Row(String label,String display,double value,List<String> options){
            this.label=label;this.display=display;this.value=value;this.options=Collections.unmodifiableList(new ArrayList<>(options));
        }
    }
    final String type,title;
    final List<Row> rows;
    private AssistantStructured(String type,String title,List<Row> rows){
        this.type=type;this.title=title;this.rows=Collections.unmodifiableList(new ArrayList<>(rows));
    }
    private static String label(String s,int max){
        s=s.strip();
        if(s.isEmpty()||s.length()>max||s.codePoints().anyMatch(x->Character.isISOControl(x)||x==0x2028||x==0x2029||
            (x>=0x202A&&x<=0x202E)||(x>=0x2066&&x<=0x2069)))throw new IllegalArgumentException("invalid_label");
        return s;
    }
    static AssistantStructured parse(String type,String body){
        if(!CHART.equals(type)&&!FORM.equals(type))throw new IllegalArgumentException("unknown_component");
        if(body==null||body.length()>12000)throw new IllegalArgumentException("component_budget");
        String[] lines=body.strip().split("\\R",-1);
        int limit=CHART.equals(type)?12:8;
        if(lines.length<2||lines.length>limit+1)throw new IllegalArgumentException("row_count");
        String[] title=lines[0].split("\\|",-1);
        if(title.length!=2||!title[0].equals("title"))throw new IllegalArgumentException("missing_title");
        List<Row> rows=new ArrayList<>();HashSet<String> labels=new HashSet<>();
        for(int i=1;i<lines.length;i++){
            String[] fields=lines[i].split("\\|",-1);
            if(fields.length<3)throw new IllegalArgumentException("invalid_row");
            String name=label(fields[1],160);
            if(!labels.add(name))throw new IllegalArgumentException("duplicate_label");
            if(CHART.equals(type)){
                if(fields.length!=3||!fields[0].equals("bar"))throw new IllegalArgumentException("invalid_bar");
                String display=fields[2].strip();
                if(!display.matches("[0-9]{1,15}(\\.[0-9]{1,8})?"))throw new IllegalArgumentException("invalid_value");
                double v=Double.parseDouble(display);
                rows.add(new Row(name,display,v,Collections.emptyList()));
            }else{
                if(!fields[0].equals("question")||fields.length<4||fields.length>8)throw new IllegalArgumentException("invalid_question");
                List<String> options=new ArrayList<>();
                for(int j=2;j<fields.length;j++){
                    String option=label(fields[j],120);
                    if(options.contains(option))throw new IllegalArgumentException("duplicate_option");
                    options.add(option);
                }
                rows.add(new Row(name,"",0,options));
            }
        }
        return new AssistantStructured(type,label(title[1],160),rows);
    }
    double fraction(int index){
        double max=0;for(Row row:rows)max=Math.max(max,row.value);
        return max==0?0:rows.get(index).value/max;
    }
    String submission(List<Integer> choices){
        if(!type.equals(FORM)||choices.size()!=rows.size())throw new IllegalArgumentException("invalid_selection");
        StringBuilder text=new StringBuilder("My selections for ").append(title).append(":\n");
        for(int i=0;i<rows.size();i++){
            Row row=rows.get(i);Integer choice=choices.get(i);
            if(choice==null||choice<0||choice>=row.options.size())throw new IllegalArgumentException("missing_selection");
            text.append("- ").append(row.label).append(": ").append(row.options.get(choice)).append('\n');
        }
        return text.toString().stripTrailing();
    }
    /** Only complete, top-level exact fenced blocks are recognized. */
    static String singleBlock(String source,String type){
        String fence="";StringBuilder body=null;String found=null;int count=0;
        for(String line:source.split("\\R",-1)){
            if(fence.isEmpty()){
                if(line.startsWith("```")){
                    int n=0;while(n<line.length()&&line.charAt(n)=='`')n++;
                    fence=line.substring(0,n);
                    if(n==3&&line.equals(fence+type)){body=new StringBuilder();count++;}
                }
            }else if(line.equals(fence)){
                if(body!=null){found=body.toString();body=null;}
                fence="";
            }else if(body!=null){body.append(line).append('\n');if(body.length()>12000)return null;}
        }
        return count==1&&body==null?found:null;
    }
}
