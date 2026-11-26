package com.asterion.control;
public final class TransferCapacityPolicyTest {
    public static void main(String[] args){
        for(String phase:new String[]{"receiving","verifying","publishing","unknown"})
            if(!TransferCapacityPolicy.isActive(phase))throw new AssertionError(phase);
        for(String phase:new String[]{"completed","failed","cancelled"})
            if(TransferCapacityPolicy.isActive(phase))throw new AssertionError(phase);
        long slots=java.util.stream.Stream.of("completed","completed","completed","completed","receiving")
            .filter(TransferCapacityPolicy::isActive).count();
        if(slots!=1)throw new AssertionError("Retained receipts occupy slots");
        System.out.println("Transfer capacity: 8 assertions passed");
    }
}
