package com.asterion.control;
public final class TransferCapacityPolicyTest {
    public static void main(String[] args){
        for(String phase:new String[]{"receiving","verifying","publishing","unknown"})
            if(!TransferCapacityPolicy.isActive(phase))throw new AssertionError(phase);
        for(String phase:new String[]{"completed","failed","cancelled","outcome_unknown"})
            if(TransferCapacityPolicy.isActive(phase))throw new AssertionError(phase);
        long slots=java.util.stream.Stream.of("completed","completed","completed","completed","receiving")
            .filter(TransferCapacityPolicy::isActive).count();
        if(slots!=1)throw new AssertionError("Retained receipts occupy slots");
        check("receive","receiving",true,8,4,10,false,false);
        check("failed","receiving",true,3,4,10,false,false);
        check("failed","receiving",false,0,4,10,false,false);
        check("verify","verifying",true,10,10,10,false,false);
        check("failed","verifying",true,8,10,10,false,false);
        check("unknown","publishing",true,10,10,10,false,false);
        check("reconcile","publishing",true,10,10,10,true,false);
        check("retain","completed",false,0,10,10,true,true);
        check("reconcile","completed",false,0,10,10,true,false);
        check("unknown","outcome_unknown",true,10,10,10,false,false);
        check("retain","failed",false,0,0,10,false,false);
        check("invalid","unrecognized",true,10,10,10,true,true);
        System.out.println("Transfer capacity and restart reconciliation: 21 assertions passed");
    }
    private static void check(String expected,String phase,boolean staged,long actual,long recorded,long size,boolean uri,boolean receipt){
        String result=TransferCapacityPolicy.recoveryAction(phase,staged,actual,recorded,size,uri,receipt);
        if(!expected.equals(result))throw new AssertionError(phase+": "+result);
    }
}
