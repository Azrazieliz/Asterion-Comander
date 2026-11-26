package com.asterion.control;

/** Active work and retained reconciliation receipts are separate capacities. */
final class TransferCapacityPolicy {
    private TransferCapacityPolicy(){}
    static boolean isActive(String phase){
        // Fail closed on unknown states; only known terminal receipts free slots.
        return !"completed".equals(phase)&&!"failed".equals(phase)&&!"cancelled".equals(phase);
    }
}
