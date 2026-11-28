package com.asterion.control;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/** A pure, bounded local arithmetic tool. Model text is only data, never code. */
final class AssistantCalculator {
    static final String FENCE="asterion_calculation";
    static final String GUIDANCE="When actual arithmetic is needed, request the local calculator by one complete fenced asterion_calculation block containing exactly expression|EXPRESSION. Use decimal numbers, parentheses, + - * / % and ^ with integer exponent from -100 to 100. Do not invent the computed value; the local tool will append its actual result.";
    private static final MathContext MC=new MathContext(34,RoundingMode.HALF_EVEN);
    private final String input;
    private int index,depth,operations;
    private AssistantCalculator(String input){
        if(input==null||input.length()>512||input.isBlank())throw new IllegalArgumentException("invalid_expression_length");
        this.input=input;
    }
    static String calculate(String expression){
        AssistantCalculator p=new AssistantCalculator(expression);
        BigDecimal value=p.expression();
        p.space();
        if(p.index!=p.input.length())throw new IllegalArgumentException("unexpected_calculator_token");
        value=bounded(value).stripTrailingZeros();
        if(value.signum()==0)return "0";
        int magnitude=value.precision()-value.scale()-1;
        return magnitude>120||magnitude<-100?value.toEngineeringString():value.toPlainString();
    }
    private static BigDecimal bounded(BigDecimal x){
        if(Math.abs((long)x.precision()-x.scale())>1000)throw new ArithmeticException("calculation_magnitude_limit");
        return x;
    }
    private void count(){if(++operations>128)throw new IllegalArgumentException("calculation_operation_limit");}
    private void space(){while(index<input.length()&&(input.charAt(index)==' '||input.charAt(index)=='\t'))index++;}
    private boolean take(char c){space();if(index<input.length()&&input.charAt(index)==c){index++;return true;}return false;}
    private BigDecimal expression(){
        BigDecimal x=term();
        while(true){
            if(take('+')){count();x=bounded(x.add(term(),MC));}
            else if(take('-')){count();x=bounded(x.subtract(term(),MC));}
            else return x;
        }
    }
    private BigDecimal term(){
        BigDecimal x=unary();
        while(true){
            if(take('*')){count();x=bounded(x.multiply(unary(),MC));}
            else if(take('/')){count();x=bounded(x.divide(unary(),MC));}
            else if(take('%')){count();x=bounded(x.remainder(unary(),MC));}
            else return x;
        }
    }
    private BigDecimal unary(){
        if(++depth>24)throw new IllegalArgumentException("calculation_depth_limit");
        try{
            if(take('+')){count();return unary();}
            if(take('-')){count();return unary().negate(MC);}
            BigDecimal x=atom();
            if(take('^')){
                count();int power=unary().intValueExact();
                if(power<-100||power>100)throw new ArithmeticException("calculation_power_limit");
                x=bounded(power<0?BigDecimal.ONE.divide(x.pow(-power,MC),MC):x.pow(power,MC));
            }
            return x;
        }finally{depth--;}
    }
    private BigDecimal atom(){
        if(take('(')){
            BigDecimal x=expression();
            if(!take(')'))throw new IllegalArgumentException("missing_closing_parenthesis");
            return x;
        }
        space();int start=index,digits=0;boolean point=false;
        while(index<input.length()){
            char c=input.charAt(index);
            if(c>='0'&&c<='9'){digits++;index++;}
            else if(c=='.'&&!point){point=true;index++;}
            else break;
        }
        if(digits==0||digits>64)throw new IllegalArgumentException("invalid_decimal");
        return bounded(new BigDecimal(input.substring(start,index),MC));
    }
    static String attachResult(String response){
        String body=AssistantStructured.singleBlock(response,FENCE);
        if(body==null)return response;
        String line=body.strip();
        if(!line.startsWith("expression|")||line.indexOf('\n')>=0||line.indexOf('\r')>=0)
            return response+"\n\nLocal calculator: invalid expression request; no result.";
        String expression=line.substring("expression|".length()).strip();
        try{
            return response+"\n\n**Local calculator result:** "+calculate(expression)+"\n";
        }catch(IllegalArgumentException|ArithmeticException invalid){
            return response+"\n\nLocal calculator: expression could not be evaluated within its supported arithmetic bounds.";
        }
    }
}
