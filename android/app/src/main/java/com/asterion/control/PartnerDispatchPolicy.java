package com.asterion.control;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** Limits the existing signed partner Binder transport; no secondary dispatcher. */
final class PartnerDispatchPolicy {
  private PartnerDispatchPolicy(){}
  static boolean approved(String expected,String current,String signer){
    return expected!=null&&!expected.isEmpty()&&expected.equals(current)&&expected.equals(signer);
  }
  static ThreadPoolExecutor executor(){
    return new ThreadPoolExecutor(2,2,0L,TimeUnit.MILLISECONDS,
        new ArrayBlockingQueue<>(8),new ThreadPoolExecutor.AbortPolicy());
  }
}
