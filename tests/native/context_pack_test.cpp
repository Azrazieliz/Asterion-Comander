#include "context_pack.h"
#include <cassert>
#include <iostream>
int main(){
    ContextPack out;
    auto fit=[](const std::string& system,int first){return system.size()+size_t(5-first)*4<=20;};
    assert(pack_context("base",{"large reference that cannot fit","ok"},5,fit,out));
    assert(out.system=="base\nok"&&out.omitted_blocks==1&&out.first_message==2);
    assert(pack_context("base",{},5,fit,out)&&out.first_message==2);
    assert(!pack_context("mandatory system too long",{},5,fit,out));
    assert(!pack_context("base",{},4,fit,out));
    assert(pack_context("base",{"a","b"},1,[](const std::string&s,int){return s.size()<=6;},out));
    assert(out.system=="base\na"&&out.omitted_blocks==1&&out.first_message==0);
    std::cout<<"Context pack behavior passed\n";
}
