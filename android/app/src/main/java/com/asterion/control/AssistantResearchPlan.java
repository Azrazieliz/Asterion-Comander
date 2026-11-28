package com.asterion.control;

/** Proposal only; a reviewed search goes to the existing Browser and configured
 * search provider. No background fetch, arbitrary URL or execution permission. */
final class AssistantResearchPlan {
    static final String FENCE="asterion_research";
    static final String GUIDANCE="For current external evidence unavailable locally, propose a focused web search in one complete fenced asterion_research block containing exactly query|SEARCH TERMS. The owner reviews the query before opening the existing browser. Do not claim the search or source retrieval already happened; use only actually captured sources for citations.";
    private AssistantResearchPlan(){}
    static String query(String value){
        if(value==null)throw new IllegalArgumentException("research_query_missing");
        String q=value.strip();
        if(q.isEmpty()||q.length()>500||q.codePoints().anyMatch(c->Character.isISOControl(c)||c==0x2028||c==0x2029||
            (c>=0x202A&&c<=0x202E)||(c>=0x2066&&c<=0x2069)))
            throw new IllegalArgumentException("invalid_research_query");
        return q;
    }
    static String parse(String response){
        String body=AssistantStructured.singleBlock(response,FENCE);
        if(body==null)return null;
        String line=body.strip();
        if(!line.startsWith("query|"))throw new IllegalArgumentException("invalid_research_proposal");
        return query(line.substring(6));
    }
}
