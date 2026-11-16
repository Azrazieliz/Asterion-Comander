#include <jni.h>
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>
#include "llama.h"

// On-phone only. Model lives in Control's private storage, never Windows.
static std::mutex guard;
static llama_model * model = nullptr;
static bool initialized = false;
static std::atomic<bool> cancel_generation{false};

extern "C" JNIEXPORT void JNICALL
Java_com_asterion_control_OnDeviceLlm_nativeCancel(JNIEnv *,jclass){
    cancel_generation.store(true,std::memory_order_release);
}
extern "C" JNIEXPORT void JNICALL
Java_com_asterion_control_OnDeviceLlm_nativeResetCancel(JNIEnv *,jclass){
    cancel_generation.store(false,std::memory_order_release);
}
extern "C" JNIEXPORT jboolean JNICALL
Java_com_asterion_control_OnDeviceLlm_nativeLoad(JNIEnv *env, jclass, jstring jpath) {
    if (!jpath) return JNI_FALSE;
    std::lock_guard<std::mutex> lock(guard);
    if (!initialized) { llama_backend_init(); initialized=true; }
    const char *path=env->GetStringUTFChars(jpath,nullptr);
    if (!path) return JNI_FALSE;
    llama_model_params params=llama_model_default_params();
    params.n_gpu_layers=0; // llama.cpp owns model mmap defaults in this API revision
    llama_model *newModel=llama_model_load_from_file(path,params);
    env->ReleaseStringUTFChars(jpath,path);
    if (!newModel) return JNI_FALSE;
    if (model) llama_model_free(model);
    model=newModel;
    return JNI_TRUE;
}
extern "C" JNIEXPORT jboolean JNICALL
Java_com_asterion_control_OnDeviceLlm_nativeReady(JNIEnv *, jclass) {
    std::lock_guard<std::mutex> lock(guard);
    return model ? JNI_TRUE : JNI_FALSE;
}
extern "C" JNIEXPORT void JNICALL
Java_com_asterion_control_OnDeviceLlm_nativeUnload(JNIEnv *, jclass) {
    std::lock_guard<std::mutex> lock(guard);
    if (model) {llama_model_free(model);model=nullptr;}
}
static void batch_tokens(llama_batch_ext *batch,const llama_token *token,int n,llama_pos first) {
    llama_batch_ext_clear(batch);
    for(int i=0;i<n;i++){
        int idx=llama_batch_ext_add_token(batch,0,token[i]);
        llama_pos at=first+i;
        llama_batch_ext_set_pos(batch,idx,&at);
    }
    llama_batch_ext_set_output_logits(batch,n-1,true);
}
extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_asterion_control_OnDeviceLlm_nativeGenerate(JNIEnv *env,jclass,jstring jprompt,jint limit) {
    if (!jprompt || limit<1 || limit>384) return nullptr;
    std::lock_guard<std::mutex> lock(guard);
    if (!model || cancel_generation.load(std::memory_order_acquire)) return nullptr;
    const char *raw=env->GetStringUTFChars(jprompt,nullptr);
    if(!raw)return nullptr;
    std::string prompt(raw);
    env->ReleaseStringUTFChars(jprompt,raw);
    if(prompt.empty()||prompt.size()>8192)return nullptr;
    const llama_vocab *vocab=llama_model_get_vocab(model);
    int tokenCount=llama_tokenize(vocab,prompt.data(),prompt.size(),nullptr,0,true,true);
    if(tokenCount>=0||tokenCount < -2048)return nullptr;
    std::vector<llama_token> tokens(-tokenCount);
    if(llama_tokenize(vocab,prompt.data(),prompt.size(),tokens.data(),tokens.size(),true,true)<0)
        return nullptr;
    llama_context_params cp=llama_context_default_params();
    cp.n_ctx=std::max(2048,(int)tokens.size()+(int)limit+32);
    cp.n_batch=std::max(256,(int)tokens.size());
    cp.n_ubatch=256;
    cp.n_threads=4;cp.n_threads_batch=4;
    llama_context *ctx=llama_init_from_model(model,cp);
    if(!ctx)return nullptr;
    llama_sampler *sampler=llama_sampler_chain_init(llama_sampler_chain_default_params());
    if(!sampler){llama_free(ctx);return nullptr;}
    llama_sampler_chain_add(sampler,llama_sampler_init_greedy());
    llama_batch_ext *batch=llama_batch_ext_init(ctx);
    if(!batch){llama_sampler_free(sampler);llama_free(ctx);return nullptr;}
    bool ok=true;
    int pos=0;
    for(int start=0;start<(int)tokens.size();start+=256){
        if(cancel_generation.load(std::memory_order_acquire)){ok=false;break;}
        int n=std::min(256,(int)tokens.size()-start);
        batch_tokens(batch,tokens.data()+start,n,start);
        if(llama_process(ctx,LLAMA_PROCESS_TYPE_DECODE,batch)!=0){ok=false;break;}
        pos+=n;
    }
    std::string answer;
    for(int i=0;ok&&i<limit;i++){
        if(cancel_generation.load(std::memory_order_acquire)){ok=false;break;}
        llama_token next=llama_sampler_sample(sampler,ctx,-1);
        if(llama_vocab_is_eog(vocab,next))break;
        char piece[1024];
        int len=llama_token_to_piece(vocab,next,piece,sizeof(piece),0,true);
        if(len<0||len>(int)sizeof(piece)){ok=false;break;}
        answer.append(piece,len);
        batch_tokens(batch,&next,1,pos++);
        if(llama_process(ctx,LLAMA_PROCESS_TYPE_DECODE,batch)!=0){ok=false;break;}
    }
    llama_batch_ext_free(batch);llama_sampler_free(sampler);llama_free(ctx);
    if(!ok||answer.size()>65536)return nullptr;
    jbyteArray bytes=env->NewByteArray(answer.size());
    if(bytes)env->SetByteArrayRegion(bytes,0,answer.size(),(jbyte*)answer.data());
    return bytes;
}
