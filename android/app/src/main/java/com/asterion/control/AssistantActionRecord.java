package com.asterion.control;

/** Immutable local observation of an explicitly authorized signed-partner request.
 * Provider status is not independent verification of the requested artifact.
 * No payload, secret, or arbitrary provider result text enters model context.
 */
final class AssistantActionRecord {
    final String requestId,appPackage,action,submission,observation;
    AssistantActionRecord(String id,String pkg,String name,String sent,String seen){
        if(!id.matches("assistant-[a-f0-9-]{36}")||!pkg.matches("[A-Za-z0-9_.]{1,200}")||
            !name.matches("[a-z][a-z0-9_.-]{0,79}"))throw new IllegalArgumentException("invalid_action_identity");
        requestId=id;appPackage=pkg;action=name;submission=status(sent);observation=status(seen);
    }
    private static String status(String value){return value!=null&&value.matches("[a-z_]{2,35}")?value:"outcome_unknown";}
    AssistantActionRecord submitted(String value){return new AssistantActionRecord(requestId,appPackage,action,value,observation);}
    AssistantActionRecord observed(String value){return new AssistantActionRecord(requestId,appPackage,action,submission,value);}
    String evidence(){
        return "Signed partner request "+requestId+" | "+appPackage+" / "+action+
            " | submission: "+submission+" | provider observation: "+observation+
            " | output not independently verified.";
    }
}
