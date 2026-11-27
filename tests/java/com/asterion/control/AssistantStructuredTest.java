package com.asterion.control;
import java.util.List;

public final class AssistantStructuredTest {
    private static int checks;
    static void check(boolean yes){checks++;if(!yes)throw new AssertionError("check "+checks);}
    static void reject(String type,String text){
        try{AssistantStructured.parse(type,text);throw new AssertionError("invalid input admitted");}
        catch(IllegalArgumentException expected){checks++;}
    }
    public static void main(String[] args){
        var chart=AssistantStructured.parse("asterion_chart","title|Costs €\nbar|A|2.5\nbar|B|5\nbar|C|0");
        check(chart.title.equals("Costs €"));check(chart.fraction(0)==.5);check(chart.fraction(1)==1);check(chart.fraction(2)==0);
        check(AssistantStructured.parse("asterion_chart","title|Empty\nbar|A|0").fraction(0)==0);
        for(String value:List.of("-1","NaN","Infinity","1e9","1,5","1|2","1000000000000000"))
            reject("asterion_chart","title|Chart\nbar|A|"+value);
        reject("asterion_chart","title|Chart\nbar|A|1\nbar|A|2");
        reject("asterion_chart","title|Chart\nbar|A|1\ncommand|run|x");
        reject("asterion_chart","title|Chart\nbar|\u202eA|1");
        var form=AssistantStructured.parse("asterion_form","title|Décisions\nquestion|Langue|Français|English\nquestion|Mode|Deep|Fast");
        check(form.submission(List.of(0,1)).equals("My selections for Décisions:\n- Langue: Français\n- Mode: Fast"));
        try{form.submission(List.of(-1,0));throw new AssertionError("incomplete accepted");}catch(IllegalArgumentException expected){checks++;}
        reject("asterion_form","title|Form\nquestion|Q|A|A");
        reject("asterion_form","title|Form\nquestion|Q|A");
        reject("asterion_form","title|Form\nquestion|Q|A|B|C|D|E|F|G");
        String action="\x60\x60\x60asterion_action\n{}\n\x60\x60\x60";
        check("{}".equals(AssistantStructured.singleBlock(action,"asterion_action").trim()));
        check(AssistantStructured.singleBlock(action+"\n"+action,"asterion_action")==null);
        check(AssistantStructured.singleBlock("\x60\x60\x60\x60text\n"+action+"\n\x60\x60\x60\x60","asterion_action")==null);
        check(AssistantStructured.singleBlock(action.substring(0,action.length()-3),"asterion_action")==null);
        check(AssistantStructured.singleBlock("quoted "+action,"asterion_action")==null);
        System.out.println(checks+" structured response assertions passed");
    }
}
