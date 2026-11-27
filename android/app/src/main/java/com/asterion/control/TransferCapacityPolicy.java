package com.asterion.control;

/** Active work and retained reconciliation receipts are separate capacities. */
final class TransferCapacityPolicy {
    private TransferCapacityPolicy(){}
    static boolean isActive(String phase){
        // Fail closed on unknown states; only known terminal receipts free slots.
        return !"completed".equals(phase)&&!"failed".equals(phase)&&!"cancelled".equals(phase)&&!"outcome_unknown".equals(phase);
    }
    static String recoveryAction(String phase,boolean staged,long actual,long recorded,long size,
                                 boolean knownUri,boolean receipt){
        if("receiving".equals(phase))return staged&&actual>=recorded&&actual<=size?"receive":"failed";
        if("verifying".equals(phase))return staged&&actual==size&&recorded==size?"verify":"failed";
        if("publishing".equals(phase)||"outcome_unknown".equals(phase)||"completed".equals(phase))
            return knownUri?"reconcile":"unknown";
        if("failed".equals(phase)||"cancelled".equals(phase))return "retain";
        return "invalid";
    }
}
