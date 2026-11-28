#include "native_vision.h"
#include "llama.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <cstdlib>
int main(int argc,char **argv){
    if(argc!=7)return 2;
    int w=std::atoi(argv[3]),h=std::atoi(argv[4]);
    if(w<1||h<1||w>1024||h>1024)return 2;
    std::ifstream in(argv[5],std::ios::binary);
    std::vector<uint8_t> pixels(static_cast<size_t>(w)*h*3);
    if(!in.read(reinterpret_cast<char*>(pixels.data()),pixels.size())||in.peek()!=EOF)return 2;
    llama_backend_init();
    VisionResult result;std::string error;
    bool ok=run_native_vision(argv[1],argv[2],w,h,pixels,argv[6],2048,96,4,
        [](){return false;},[](int n){std::cerr<<"prompt_tokens="<<n<<"\n";return true;},
        [](const char*,int){return true;},result,error);
    if(ok){
        std::cout<<result.text<<"\n";
        std::cerr<<"generated_tokens="<<result.generated_tokens<<" end_of_generation="<<result.end_of_generation<<"\n";
    }else std::cerr<<error<<"\n";
    llama_backend_free();return ok?0:1;
}
