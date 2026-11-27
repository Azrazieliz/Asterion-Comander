package com.asterion.control;

/** Recovery of the existing phone-owned continuation ledger, not a new executor. */
final class CycleRecoveryPolicy {
  private CycleRecoveryPolicy(){}
  static boolean unchangedBeforeQueue(String prior,int sequence,String phase,
                                      String current,int currentSequence,String currentPhase){
    return prior!=null&&prior.equals(current)&&sequence>=0&&sequence==currentSequence&&
      phase!=null&&phase.equals(currentPhase)&&
      ("idle".equals(phase)||"acknowledged".equals(phase)||"cancelled".equals(phase)||"failed".equals(phase));
  }
  static String phaseAfterQueue(String ledger){
    if("queued".equals(ledger))return "queued";
    if("submitted_unverified".equals(ledger)||"acknowledged".equals(ledger))return "waiting_ack";
    return "needs_review";
  }
}
