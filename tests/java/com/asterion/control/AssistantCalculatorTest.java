package com.asterion.control;
public final class AssistantCalculatorTest {
    private static void equal(String expected,String actual){
        if(!expected.equals(actual))throw new AssertionError(expected+" != "+actual);
    }
    private static void rejects(String text){
        try{AssistantCalculator.calculate(text);throw new AssertionError("accepted "+text);}
        catch(IllegalArgumentException|ArithmeticException expected){}
    }
    public static void main(String[] args){
        equal("0.3",AssistantCalculator.calculate("0.1+0.2"));
        equal("48",AssistantCalculator.calculate("72/(90/60)"));
        equal("19",AssistantCalculator.calculate("3+4*4"));
        equal("28",AssistantCalculator.calculate("(3+4)*4"));
        equal("-4",AssistantCalculator.calculate("-2^2"));
        equal("0.125",AssistantCalculator.calculate("2^-3"));
        equal("512",AssistantCalculator.calculate("2^3^2"));
        equal("1",AssistantCalculator.calculate("7%3"));
        rejects("1/0");rejects("2^101");rejects("2.0.1");rejects("Math.sqrt(4)");
        rejects("(".repeat(25)+"1"+")".repeat(25));rejects("3 4");
        String fence="```";
        String request=fence+"asterion_calculation\nexpression|72/(90/60)\n"+fence;
        if(!AssistantCalculator.attachResult(request).contains("Local calculator result:** 48"))throw new AssertionError();
        AssistantCalculator.Receipt receipt=AssistantCalculator.evaluate(request);
        if(receipt==null||!receipt.ok()||!receipt.reference().contains("72/(90/60) = 48"))throw new AssertionError();
        AssistantCalculator.Receipt invalid=AssistantCalculator.evaluate(fence+"asterion_calculation\nexpression|1/0\n"+fence);
        if(invalid==null||invalid.ok())throw new AssertionError();
        try{invalid.reference();throw new AssertionError("invalid result admitted");}catch(IllegalStateException expected){}
        if(AssistantCalculator.evaluate("ordinary answer")!=null)throw new AssertionError();
        equal("ordinary answer",AssistantCalculator.attachResult("ordinary answer"));
        System.out.println("Native calculator behavior passed");
    }
}
