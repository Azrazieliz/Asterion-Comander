package com.asterion.control;
public final class AssistantSchedulePlanTest {
    static void check(boolean yes){if(!yes)throw new AssertionError();}
    public static void main(String[] args){
        long base=1000000,period=15*60000L;
        check(AssistantSchedulePlan.first(base,5)==base+300000);
        check(AssistantSchedulePlan.next(base,base,15)==base+period);
        check(AssistantSchedulePlan.next(base,base+period*10+1,15)==base+period*11);
        check(AssistantSchedulePlan.next(base,base-1,15)==base);
        check(AssistantSchedulePlan.next(base,base,0)==0);
        String fence=String.valueOf((char)96).repeat(3);
        String block=fence+"asterion_schedule\nkind|inference\ntitle|Review notes\ndelay_minutes|5\ninterval_minutes|30\nprompt|Summarize locally\n"+fence;
        check(AssistantSchedulePlan.parse(block).intervalMinutes==30);
        check(AssistantSchedulePlan.parse(block+"\n"+block)==null);
        check(AssistantSchedulePlan.parse(block.substring(0,block.length()-3))==null);
        try{AssistantSchedulePlan.parse(block.replace("interval_minutes|30","interval_minutes|1"));throw new AssertionError();}
        catch(IllegalArgumentException expected){}
        try{AssistantSchedulePlan.parse(block.replace("kind|inference","kind|shell"));throw new AssertionError();}
        catch(IllegalArgumentException expected){}
        System.out.println("Schedule plan behavior passed");
    }
}
