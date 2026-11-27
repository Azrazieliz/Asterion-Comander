package com.asterion.control;
import java.util.ArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Future;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
public final class PartnerDispatchPolicyTest {
  private static void check(boolean ok){if(!ok)throw new AssertionError();}
  public static void main(String[] args)throws Exception{
    check(PartnerDispatchPolicy.approved("a","a","a"));
    check(!PartnerDispatchPolicy.approved("a","","a"));
    check(!PartnerDispatchPolicy.approved("a","b","a"));
    check(!PartnerDispatchPolicy.approved("a","a","b"));
    check(!PartnerDispatchPolicy.approved("","",""));
    ThreadPoolExecutor executor=PartnerDispatchPolicy.executor();
    CountDownLatch started=new CountDownLatch(2),release=new CountDownLatch(1);
    try{
      for(int i=0;i<2;i++)executor.submit(()->{started.countDown();release.await();return null;});
      check(started.await(5,TimeUnit.SECONDS));
      ArrayList<Future<?>> queued=new ArrayList<>();
      for(int i=0;i<8;i++)queued.add(executor.submit(()->{}));
      check(executor.getQueue().size()==8);
      try{executor.submit(()->{});throw new AssertionError("unbounded queue");}
      catch(RejectedExecutionException expected){}
      check(queued.get(0).cancel(true));
      executor.purge();
      check(executor.getQueue().size()==7);
      Future<?> replacement=executor.submit(()->{});
      release.countDown();
      replacement.get(5,TimeUnit.SECONDS);
      check(queued.get(0).isCancelled());
    }finally{release.countDown();executor.shutdownNow();}
    System.out.println("PartnerDispatchPolicy: approval, saturation and cancellation passed");
  }
}
