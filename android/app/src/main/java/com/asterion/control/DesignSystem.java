package com.asterion.control;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Original Asterion Control visual language, entirely native Android. */
public final class DesignSystem {
  private DesignSystem() {}
  public static final int BG=0xFF080B16,SURFACE=0xFF151B30,SURFACE2=0xFF232B45;
  public static final int EDGE=0xFF343C59,TEXT=0xFFF7F8FF,MUTED=0xFFA0ADC7;
  public static final int PURPLE=Color.rgb(161,143,255),TEAL=Color.rgb(76,227,206),WARNING=Color.rgb(255,187,112),BAD=Color.rgb(255,118,143);
  public static int dp(Context c,float x){return (int)(x*c.getResources().getDisplayMetrics().density+0.5f);}
  public static GradientDrawable shape(Context c,int base,int stroke,int radius){
    GradientDrawable d=new GradientDrawable();d.setColor(base);d.setCornerRadius(dp(c,radius));if(stroke!=0)d.setStroke(dp(c,1),stroke);return d;
  }
  public static GradientDrawable gradient(Context c,int first,int last,int radius){
    GradientDrawable d=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{first,last});d.setCornerRadius(dp(c,radius));return d;
  }
  public static void clickable(View v,Context c,int background,int outline,int radius){
    v.setBackground(new RippleDrawable(ColorStateList.valueOf(0x4DFFFFFF),shape(c,background,outline,radius),shape(c,Color.WHITE,0,radius)));v.setClickable(true);
  }
  public static LinearLayout vertical(Context c){LinearLayout l=new LinearLayout(c);l.setOrientation(LinearLayout.VERTICAL);return l;}
  public static LinearLayout horizontal(Context c){LinearLayout l=new LinearLayout(c);l.setOrientation(LinearLayout.HORIZONTAL);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
  public static TextView text(Context c,String value,float sp,int color,boolean heavy){
    TextView t=new TextView(c);t.setText(value);t.setTextColor(color);t.setTextSize(sp);
    t.setTypeface(Typeface.create(heavy?"sans-serif-medium":"sans-serif",heavy?Typeface.BOLD:Typeface.NORMAL));t.setIncludeFontPadding(false);
    return t;
  }
  public static TextView eyebrow(Context c,String value){TextView t=text(c,value,10,MUTED,true);t.setLetterSpacing(.18f);return t;}
  public static LinearLayout card(Context c){
    LinearLayout card=vertical(c);card.setPadding(dp(c,17),dp(c,18),dp(c,17),dp(c,18));
    card.setBackground(shape(c,SURFACE,EDGE,22));return card;
  }
  public static TextView pill(Context c,String label,int color){
    TextView t=text(c,label,11,color,true);t.setGravity(Gravity.CENTER);t.setPadding(dp(c,11),dp(c,7),dp(c,11),dp(c,7));
    GradientDrawable b=shape(c,color==TEAL?0xFF143835:color==BAD?0xFF3A2033:0xFF2F2949,0,40);
    t.setBackground(b);return t;
  }

  /** Accessible visual resource meter with measured, not estimated, data. */
  public static final class Meter extends View {
    final Paint brush=new Paint(3);float value=0f;final int accent;
    public Meter(Context context,int color){super(context);accent=color;setMinimumHeight(dp(context,11));}
    public void setProgress(float p){value=Math.min(1f,Math.max(0f,p));invalidate();}
    @Override protected void onMeasure(int widthSpec,int heightSpec){setMeasuredDimension(MeasureSpec.getSize(widthSpec),dp(getContext(),11));}
    @Override protected void onDraw(Canvas c){super.onDraw(c);float h=getHeight(),w=getWidth();
      brush.setShader(null);brush.setColor(0xFF30384D);brush.setStyle(Paint.Style.FILL);c.drawRoundRect(0,0,w,h,h/2,h/2,brush);
      if(value>0.001f){float fill=Math.max(h,w*value);brush.setShader(new LinearGradient(0,0,fill,0,new int[]{accent,0xFF8DA1FF},null,Shader.TileMode.CLAMP));
      c.drawRoundRect(0,0,Math.min(fill,w),h,h/2,h/2,brush);brush.setShader(null);}
    }
  }
  public static final class AsterionMark extends View {
    Paint p=new Paint(3);public AsterionMark(Context c){super(c);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
    @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);float s=Math.min(getWidth(),getHeight());canvas.save();canvas.translate((getWidth()-s)/2f,(getHeight()-s)/2f);canvas.scale(s/56f,s/56f);
      p.setStyle(Paint.Style.FILL);p.setShader(new LinearGradient(0,0,56,56,new int[]{0xFF7962F6,0xFF2EC9DB},null,Shader.TileMode.CLAMP));canvas.drawRoundRect(new RectF(0,0,56,56),18,18,p);p.setShader(null);
      p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(2.2f);p.setColor(0xDDFBFBFF);canvas.save();canvas.rotate(-28,28,28);canvas.drawOval(12,23,44,33,p);canvas.restore();
      p.setStyle(Paint.Style.FILL);Path a=new Path();a.moveTo(28,12);a.lineTo(44,42);a.lineTo(36.5f,42);a.lineTo(28,24);a.lineTo(19.5f,42);a.lineTo(12,42);a.close();canvas.drawPath(a,p);
      p.setColor(0xFF6B62D6);canvas.drawCircle(28,34.8f,3.3f,p);canvas.restore();
    }
  }
  public static final class Icon extends View {
    final String kind;final Paint p=new Paint(3);int tint;
    public Icon(Context c,String kind,int tint){super(c);this.kind=kind;this.tint=tint;setMinimumWidth(dp(c,24));setMinimumHeight(dp(c,24));}
    public void tint(int color){tint=color;invalidate();}
    @Override protected void onDraw(Canvas real){super.onDraw(real);float s=Math.min(getWidth(),getHeight());real.save();real.translate((getWidth()-s)/2f,(getHeight()-s)/2f);real.scale(s/24f,s/24f);Canvas c=real;
      p.setColor(tint);p.setStrokeWidth(1.9f);p.setStrokeCap(Paint.Cap.ROUND);p.setStrokeJoin(Paint.Join.ROUND);p.setStyle(Paint.Style.STROKE);
      switch(kind){
        case "home":line(c,3,10.3f,12,3);line(c,12,3,21,10.3f);line(c,5,9.3f,5,20);line(c,19,9.3f,19,20);line(c,5,20,19,20);c.drawRoundRect(10,13,14,20,1,1,p);break;
        case "monitor":c.drawRoundRect(2.5f,4,21.5f,17,2.3f,2.3f,p);line(c,12,17,12,21);line(c,7,21,17,21);break;
        case "pulse":{Path path=new Path();path.moveTo(2,12);path.lineTo(6,12);path.lineTo(9,6);path.lineTo(12.6f,18);path.lineTo(16,10);path.lineTo(18,12);path.lineTo(22,12);c.drawPath(path,p);break;}
        case "devices":c.drawRoundRect(2.5f,4,16,16,2,2,p);line(c,6,20,15,20);line(c,11,16,11,20);c.drawRoundRect(16,9,22,20,1.2f,1.2f,p);break;
        case "phone":c.drawRoundRect(7,2,17,22,2,2,p);line(c,10.5f,18,13.5f,18);break;
        case "settings":c.drawCircle(12,12,7,p);c.drawCircle(12,12,2.5f,p);line(c,12,1,12,5);line(c,12,19,12,23);line(c,1,12,5,12);line(c,19,12,23,12);break;
        case "arrow":line(c,4,12,20,12);line(c,14,6,20,12);line(c,14,18,20,12);break;
        case "refresh":c.drawArc(4,4,20,20,55,280,false,p);line(c,18,5,20,9);line(c,20,9,16,9);break;
        case "power":c.drawArc(4,4,20,20,-57,296,false,p);line(c,12,2,12,12);break;
        case "wifi":{Path path=new Path();path.moveTo(2,8);path.quadTo(12,-1,22,8);path.moveTo(5.5f,12);path.quadTo(12,6,18.5f,12);path.moveTo(9,16);path.quadTo(12,13,15,16);c.drawPath(path,p);p.setStyle(Paint.Style.FILL);c.drawCircle(12,20,1.4f,p);break;}
        case "shield":{Path path=new Path();path.moveTo(12,2);path.lineTo(20,5);path.lineTo(19,13);path.quadTo(17,19,12,22);path.quadTo(7,19,5,13);path.lineTo(4,5);path.close();c.drawPath(path,p);line(c,9,12,11.3f,14.3f);line(c,11.3f,14.3f,16,9.5f);break;}
        case "share":{c.drawRoundRect(5,8,19,22,2,2,p);line(c,12,16,12,2);line(c,7,7,12,2);line(c,17,7,12,2);break;}
        case "battery":c.drawRoundRect(2,6,20,18,2,2,p);line(c,22,10,22,14);p.setStyle(Paint.Style.FILL);c.drawRoundRect(5,9,14,15,1,1,p);break;
        case "storage":c.drawRoundRect(3,4,21,20,3,3,p);line(c,3,11,21,11);p.setStyle(Paint.Style.FILL);c.drawCircle(17,16,1,p);break;
        case "copy":c.drawRoundRect(8,7,20,21,2,2,p);c.drawRoundRect(4,3,16,17,2,2,p);break;
        case "check":line(c,4,12,10,18);line(c,10,18,20,6);break;
        case "activity":{Path q=new Path();q.moveTo(2,16);q.lineTo(7,11);q.lineTo(10,14);q.lineTo(16,6);q.lineTo(22,8);c.drawPath(q,p);break;}
        default:c.drawCircle(12,12,7,p);
      }
      real.restore();
    }
    private void line(Canvas c,float x1,float y1,float x2,float y2){c.drawLine(x1,y1,x2,y2,p);}
  }
}
