package com.asterion.control;

import android.content.Context;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.graphics.Typeface;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.StyleSpan;
import android.text.style.TypefaceSpan;
import android.text.style.URLSpan;
import android.text.method.LinkMovementMethod;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TableLayout;
import android.widget.TableRow;
import android.widget.TextView;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Native Markdown rendering. No HTML/WebView script execution or remote image fetches. */
final class AssistantMarkdown {
    private AssistantMarkdown(){}
    static void render(Context c,LinearLayout parent,String source,int text,int muted,int panel){
        String[] lines=source.split("\n",-1);
        for(int at=0;at<lines.length;){
            String line=lines[at];
            if(line.startsWith("```")){
                String language=line.substring(3).trim();StringBuilder code=new StringBuilder();at++;
                while(at<lines.length&&!lines[at].startsWith("```")){if(code.length()>0)code.append('\n');code.append(lines[at++]);}
                if(at<lines.length)at++;
                LinearLayout box=DesignSystem.vertical(c);box.setPadding(dp(c,12),dp(c,8),dp(c,12),dp(c,12));
                box.setBackground(DesignSystem.shape(c,panel,0,12));
                TextView copy=DesignSystem.text(c,language.isEmpty()?"Copy code":language+" · Copy",12,muted,true);
                copy.setMinHeight(dp(c,48));copy.setGravity(android.view.Gravity.CENTER_VERTICAL);
                String value=code.toString();copy.setOnClickListener(v->{
                    ((ClipboardManager)c.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Code",value));});
                box.addView(copy);HorizontalScrollView scroll=new HorizontalScrollView(c);
                TextView body=DesignSystem.text(c,value,14,text,false);body.setTypeface(Typeface.MONOSPACE);body.setTextIsSelectable(true);
                scroll.addView(body);box.addView(scroll);add(parent,box,8);continue;
            }
            if(at+1<lines.length&&line.contains("|")&&lines[at+1].trim().matches("\\|?\\s*:?-{3,}.*\\|.*")){
                TableLayout table=new TableLayout(c);int row=0;
                while(at<lines.length&&lines[at].contains("|")){
                    String entry=lines[at++].trim();if(entry.matches("[| :\\-]+"))continue;
                    if(entry.startsWith("|"))entry=entry.substring(1);if(entry.endsWith("|"))entry=entry.substring(0,entry.length()-1);
                    TableRow tr=new TableRow(c);
                    for(String cell:entry.split("\\|",-1)){
                        TextView v=DesignSystem.text(c,"",14,text,row==0);v.setText(inline(cell.trim()));
                        v.setTextIsSelectable(true);v.setPadding(dp(c,12),dp(c,10),dp(c,12),dp(c,10));
                        v.setBackground(DesignSystem.shape(c,panel,muted,0));tr.addView(v);
                    }table.addView(tr);row++;
                }
                HorizontalScrollView scroll=new HorizontalScrollView(c);scroll.addView(table);add(parent,scroll,8);continue;
            }
            if(line.isBlank()){at++;continue;}
            int heading=0;while(heading<line.length()&&line.charAt(heading)=='#')heading++;
            boolean isHeading=heading>0&&heading<=6&&line.length()>heading&&line.charAt(heading)==' ';
            if(isHeading)line=line.substring(heading+1);
            else if(line.startsWith("- ")||line.startsWith("* "))line="•  "+line.substring(2);
            else if(line.startsWith("> "))line="│  "+line.substring(2);
            TextView v=DesignSystem.text(c,"",isHeading?Math.max(17,25-heading*2):16,text,isHeading);
            v.setText(inline(line));v.setTextIsSelectable(true);v.setLineSpacing(dp(c,4),1);
            v.setMovementMethod(LinkMovementMethod.getInstance());add(parent,v,isHeading?14:5);at++;
        }
    }
    private static SpannableStringBuilder inline(String source){
        SpannableStringBuilder out=new SpannableStringBuilder();
        Matcher m=Pattern.compile("(`[^`]+`|\\*\\*[^*]+\\*\\*|\\[[^]\\n]+\\]\\(https?://[^\\s)]+\\))").matcher(source);
        int last=0;
        while(m.find()){
            out.append(source.substring(last,m.start()));String token=m.group();int start=out.length();
            if(token.startsWith("`")){out.append(token.substring(1,token.length()-1));out.setSpan(new TypefaceSpan("monospace"),start,out.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);}
            else if(token.startsWith("**")){out.append(token.substring(2,token.length()-2));out.setSpan(new StyleSpan(Typeface.BOLD),start,out.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);}
            else{int split=token.indexOf("](");out.append(token.substring(1,split));out.setSpan(new URLSpan(token.substring(split+2,token.length()-1)),start,out.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);}
            last=m.end();
        }out.append(source.substring(last));return out;
    }
    private static int dp(Context c,int n){return DesignSystem.dp(c,n);}
    private static void add(LinearLayout parent,android.view.View v,int margin){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=DesignSystem.dp(parent.getContext(),margin);parent.addView(v,p);}
}
