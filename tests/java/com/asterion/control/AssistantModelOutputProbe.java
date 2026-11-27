package com.asterion.control;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;

/** Calls the same native parser/data contracts used by the app. No action dispatch. */
public final class AssistantModelOutputProbe {
    private static void emit(String value){
        System.out.println(Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8)));
    }
    public static void main(String[] args)throws Exception{
        if(args.length!=1)throw new IllegalArgumentException("probe kind required");
        String input=new String(System.in.readNBytes(65537),StandardCharsets.UTF_8);
        if(input.length()>65536)throw new IllegalArgumentException("response budget");
        String kind=args[0];
        if(kind.equals("asterion_schedule")){
            AssistantSchedulePlan plan=AssistantSchedulePlan.parse(input);
            if(plan==null)throw new IllegalArgumentException("no complete proposal");
            emit(plan.kind);emit(plan.title);emit(Integer.toString(plan.delayMinutes));
            emit(Integer.toString(plan.intervalMinutes));emit(plan.prompt);return;
        }
        String body=AssistantStructured.singleBlock(input,kind);
        if(body==null)throw new IllegalArgumentException("no single complete block");
        if(kind.equals("asterion_chart")||kind.equals("asterion_form")){
            AssistantStructured component=AssistantStructured.parse(kind,body);
            emit(component.title);
            for(AssistantStructured.Row row:component.rows){
                emit(row.label);
                if(kind.equals("asterion_chart"))emit(Double.toString(row.value));
                else{
                    emit(Integer.toString(row.options.size()));
                    for(String option:row.options)emit(option);
                }
            }
        }else if(kind.equals("csv")){
            AssistantArtifact artifact=AssistantArtifact.create("csv",body.stripTrailing());
            if(artifact==null||!artifact.verified(artifact.data()))throw new IllegalArgumentException("artifact invalid");
            emit(artifact.mime);emit(new String(artifact.data(),StandardCharsets.UTF_8));
        }else if(kind.equals("asterion_action")){
            // JSON schema is checked by the Python judge. Actual provider
            // validation and invocation remain Android-only operations.
            emit(body);
        }else throw new IllegalArgumentException("unsupported probe kind");
    }
}
