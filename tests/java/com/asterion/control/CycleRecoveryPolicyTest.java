package com.asterion.control;
public final class CycleRecoveryPolicyTest {
  private static void check(boolean value){if(!value)throw new AssertionError();}
  public static void main(String[] args){
    check(CycleRecoveryPolicy.unchangedBeforeQueue("",0,"idle","",0,"idle"));
    check(CycleRecoveryPolicy.unchangedBeforeQueue("old",7,"acknowledged","old",7,"acknowledged"));
    check(!CycleRecoveryPolicy.unchangedBeforeQueue("old",7,"acknowledged","old",8,"acknowledged"));
    check(!CycleRecoveryPolicy.unchangedBeforeQueue("old",7,"acknowledged","new",7,"acknowledged"));
    check(!CycleRecoveryPolicy.unchangedBeforeQueue("old",7,"acknowledged","old",7,"queued"));
    check(!CycleRecoveryPolicy.unchangedBeforeQueue("old",7,"submitted_unverified","old",7,"submitted_unverified"));
    check(!CycleRecoveryPolicy.unchangedBeforeQueue("old",-1,"idle","old",-1,"idle"));
    check(CycleRecoveryPolicy.phaseAfterQueue("queued").equals("queued"));
    check(CycleRecoveryPolicy.phaseAfterQueue("submitted_unverified").equals("waiting_ack"));
    check(CycleRecoveryPolicy.phaseAfterQueue("acknowledged").equals("waiting_ack"));
    for(String phase:new String[]{"dispatching","requires_manual_review","cancelled","failed","idle","paused",""})
      check(CycleRecoveryPolicy.phaseAfterQueue(phase).equals("needs_review"));
    System.out.println("Cycle recovery policy passed");
  }
}
