#pragma once
#include <string>
#include <vector>
#include <utility>

// The fit function must format with the real model template and reserve output tokens.
// It never admits a partial user turn or a fragment of a source passage.
struct ContextPack {
    std::string system;
    int first_message;
    int omitted_blocks;
};
template<class Fits>
bool pack_context(const std::string &base,const std::vector<std::string> &references,
                  int count,Fits fits,ContextPack &out){
    if(count<1||count%2!=1)return false;
    ContextPack result{base,count-1,0};
    if(!fits(result.system,result.first_message))return false;
    for(const auto &ref:references){
        if(ref.empty())continue;
        std::string candidate=result.system+"\n"+ref;
        if(fits(candidate,result.first_message))result.system=std::move(candidate);
        else result.omitted_blocks++;
    }
    while(result.first_message>=2&&fits(result.system,result.first_message-2))
        result.first_message-=2;
    out=std::move(result);
    return true;
}
