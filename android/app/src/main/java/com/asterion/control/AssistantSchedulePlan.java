package com.asterion.control;

/** Fixed interval scheduling: no catch-up storm, explicit owner approval, bounded input. */
final class AssistantSchedulePlan {
    static final String FENCE="asterion_schedule";
    static final String GUIDANCE="For a requested local reminder or scheduled offline AI answer, propose one complete fenced asterion_schedule block with five lines: kind|reminder (or inference), title|short title, delay_minutes|positive integer, interval_minutes|0 for once or 15-525600 for recurring, prompt|literal text. The owner must review and approve; do not claim a schedule is active until the local UI confirms it. Scheduled inference produces a local answer, not automatic external tool actions. The existing enabled Control service must be running.";
    final String kind,title,prompt;
    final int delayMinutes,intervalMinutes;
    AssistantSchedulePlan(String kind,String title,int delay,int interval,String prompt){
        if(!"reminder".equals(kind)&&!"inference".equals(kind))throw new IllegalArgumentException("Unknown task type");
        if(title==null||title.isBlank()||title.length()>120||title.codePoints().anyMatch(Character::isISOControl))
            throw new IllegalArgumentException("Invalid title");
        if(prompt==null||prompt.isBlank()||prompt.length()>6000||prompt.indexOf('\0')>=0)
            throw new IllegalArgumentException("Invalid task instructions");
        if(delay<1||delay>525600||interval<0||interval>525600||(interval>0&&interval<15))
            throw new IllegalArgumentException("Delay must be 1–525600 minutes; recurrence 0 or 15–525600");
        this.kind=kind;this.title=title;delayMinutes=delay;intervalMinutes=interval;this.prompt=prompt;
    }
    static AssistantSchedulePlan parse(String response){
        String body=AssistantStructured.singleBlock(response,FENCE);
        if(body==null)return null;
        String[] lines=body.strip().split("\\R",-1);
        String[] keys={"kind","title","delay_minutes","interval_minutes","prompt"};
        if(lines.length!=keys.length)throw new IllegalArgumentException("Invalid schedule proposal");
        String[] values=new String[keys.length];
        for(int i=0;i<keys.length;i++){
            String prefix=keys[i]+"|";
            if(!lines[i].startsWith(prefix))throw new IllegalArgumentException("Invalid schedule field");
            values[i]=lines[i].substring(prefix.length());
        }
        if(!values[2].matches("[0-9]{1,6}")||!values[3].matches("[0-9]{1,6}"))
            throw new IllegalArgumentException("Invalid schedule interval");
        return new AssistantSchedulePlan(values[0],values[1],Integer.parseInt(values[2]),Integer.parseInt(values[3]),values[4]);
    }
    static long first(long now,int delay){return Math.addExact(now,Math.multiplyExact(delay,60000L));}
    static long next(long due,long now,int interval){
        if(interval==0)return 0;
        long period=Math.multiplyExact(interval,60000L);
        if(now<due)return due;
        return Math.addExact(due,Math.multiplyExact(1+(now-due)/period,period));
    }
}
