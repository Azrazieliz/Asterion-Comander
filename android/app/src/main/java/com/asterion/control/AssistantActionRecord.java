package com.asterion.control;

/** Immutable local observation of an explicitly authorized signed-partner request.
 * Provider status is not independent verification of the requested artifact.
 * No payload, secret, or arbitrary provider result text enters model context.
 */
final class AssistantActionRecord {
    final String requestId,appPackage,action,submission,observation,data;
    AssistantActionRecord(String id,String pkg,String name,String sent,String seen){
        this(id,pkg,name,sent,seen,"");
    }
    AssistantActionRecord(String id,String pkg,String name,String sent,String seen,String data){
        if(!id.matches("assistant-[a-f0-9-]{36}")||!pkg.matches("[A-Za-z0-9_.]{1,200}")||
            !name.matches("[a-z][a-z0-9_.-]{0,79}"))throw new IllegalArgumentException("invalid_action_identity");
        requestId=id;appPackage=pkg;action=name;submission=status(sent);observation=status(seen);
        this.data=data!=null&&data.length()<=3000?data:"";
    }
    private static String status(String value){return value!=null&&value.matches("[a-z_]{2,35}")?value:"outcome_unknown";}
    AssistantActionRecord submitted(String value){return new AssistantActionRecord(requestId,appPackage,action,value,observation,data);}
    AssistantActionRecord observed(String value){return new AssistantActionRecord(requestId,appPackage,action,submission,value,data);}
    AssistantActionRecord withData(String value){
        return value==null||value.isEmpty()?this:
            new AssistantActionRecord(requestId,appPackage,action,submission,observation,value);
    }
    String evidence(){
        return "Signed partner request "+requestId+" | "+appPackage+" / "+action+
            " | submission: "+submission+" | provider observation: "+observation+
            " | output not independently verified."+(data.isEmpty()?"":"\nBounded historical provider-reported observation: "+data);
    }
}
