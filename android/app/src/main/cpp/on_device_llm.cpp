#include <jni.h>
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>
#include "llama.h"

static std::mutex guard;
static llama_model *model=nullptr;
static bool initialized=false;
static std::atomic<bool> model_loaded{false};
static std::atomic<bool> cancel_generation{false};
extern "C" JNIEXPORT void JNICALL Java_com_asterion_control_OnDeviceLlm_nativeCancel(JNIEnv *,jclass){cancel_generation.store(true);}
extern "C" JNIEXPORT void JNICALL Java_com_asterion_control_OnDeviceLlm_nativeResetCancel(JNIEnv *,jclass){cancel_generation.store(false);}
extern "C" JNIEXPORT jboolean JNICALL Java_com_asterion_control_OnDeviceLlm_nativeLoad(JNIEnv *env,jclass,jstring jpath){
    if(!jpath)return JNI_FALSE;
    std::lock_guard<std::mutex> lock(guard);
    if(!initialized){llama_backend_init();initialized=true;}
    const char *path=env->GetStringUTFChars(jpath,nullptr);
    if(!path)return JNI_FALSE;
    llama_model_params params=llama_model_default_params();
    params.n_gpu_layers=0; // CPU verified source baseline; accelerator admission remains measured separately.
    llama_model *loaded=llama_model_load_from_file(path,params);
    env->ReleaseStringUTFChars(jpath,path);
    if(!loaded)return JNI_FALSE;
    if(model)llama_model_free(model);
    model=loaded;model_loaded.store(true);return JNI_TRUE;
}
extern "C" JNIEXPORT jboolean JNICALL Java_com_asterion_control_OnDeviceLlm_nativeReady(JNIEnv *,jclass){return model_loaded.load()?JNI_TRUE:JNI_FALSE;}
extern "C" JNIEXPORT void JNICALL Java_com_asterion_control_OnDeviceLlm_nativeUnload(JNIEnv *,jclass){std::lock_guard<std::mutex> lock(guard);if(model){model_loaded.store(false);llama_model_free(model);model=nullptr;}}
static bool read_utf8(JNIEnv *env,jbyteArray data,std::string &out){
    if(!data)return false;
    jsize n=env->GetArrayLength(data);
    if(n<1||n>262144)return false;
    out.resize(n);env->GetByteArrayRegion(data,0,n,reinterpret_cast<jbyte *>(out.data()));
    return !env->ExceptionCheck();
}
static void batch_tokens(llama_batch_ext *batch,const llama_token *token,int n,llama_pos first){
    llama_batch_ext_clear(batch);
    for(int i=0;i<n;i++){int at=llama_batch_ext_add_token(batch,0,token[i]);llama_pos pos=first+i;llama_batch_ext_set_pos(batch,at,&pos);}
    llama_batch_ext_set_output_logits(batch,n-1,true);
}
extern "C" JNIEXPORT jbyteArray JNICALL Java_com_asterion_control_OnDeviceLlm_nativeGenerate(
    JNIEnv *env,jclass,jbyteArray jsystem,jobjectArray jroles,jobjectArray jcontent,
    jint limit,jint context_limit,jobject stream){
    if(!jsystem||!jroles||!jcontent||!stream||limit<1||limit>2048||context_limit<512||context_limit>16384||limit+256>context_limit)return nullptr;
    std::lock_guard<std::mutex> lock(guard);
    if(!model||cancel_generation.load())return nullptr;
    int count=env->GetArrayLength(jroles);
    if(count<1||count>1000||count%2!=1||env->GetArrayLength(jcontent)!=count)return nullptr;
    std::string systemText;if(!read_utf8(env,jsystem,systemText))return nullptr;
    std::vector<std::string> texts(count);
    for(int i=0;i<count;i++){
        auto role=static_cast<jstring>(env->GetObjectArrayElement(jroles,i));
        if(!role)return nullptr;
        const char *raw=env->GetStringUTFChars(role,nullptr);
        if(!raw){env->DeleteLocalRef(role);return nullptr;}
        bool valid=std::string(raw)==(i%2==0?"user":"assistant");
        env->ReleaseStringUTFChars(role,raw);env->DeleteLocalRef(role);
        auto content=static_cast<jbyteArray>(env->GetObjectArrayElement(jcontent,i));
        bool readable=read_utf8(env,content,texts[i]);if(content)env->DeleteLocalRef(content);
        if(!valid||!readable)return nullptr;
    }
    const char *chatTemplate=llama_model_chat_template(model,nullptr);
    if(!chatTemplate)return nullptr;
    const llama_vocab *vocab=llama_model_get_vocab(model);
    std::string prompt;std::vector<llama_token> tokens;
    int omitted=0;
    // Retain exact full history in encrypted storage. Pack complete exchanges by
    // actual native token count; never cut a user message or pretend it all fits.
    for(;;){
        if(cancel_generation.load())return nullptr;
        std::vector<llama_chat_message> messages={{"system",systemText.c_str()}};
        size_t bytes=systemText.size();
        for(int i=omitted;i<count;i++){
            bytes+=texts[i].size();
            messages.push_back({i%2==0?"user":"assistant",texts[i].c_str()});
        }
        if(bytes>262144){if(omitted+2<count){omitted+=2;continue;}return nullptr;}
        std::vector<char> formatted(std::min<size_t>(524288,bytes*2+4096));
        int written=llama_chat_apply_template(chatTemplate,messages.data(),messages.size(),true,formatted.data(),formatted.size());
        if(written<=0||written>524287)return nullptr;
        if(static_cast<size_t>(written)>=formatted.size()){
            formatted.resize(written+1);
            written=llama_chat_apply_template(chatTemplate,messages.data(),messages.size(),true,formatted.data(),formatted.size());
            if(written<=0||static_cast<size_t>(written)>=formatted.size())return nullptr;
        }
        prompt.assign(formatted.data(),written);
        int n=llama_tokenize(vocab,prompt.data(),prompt.size(),nullptr,0,true,true);
        if(n>=0||n < -524288)return nullptr;
        if(static_cast<size_t>(-n)+static_cast<size_t>(limit)+32u>static_cast<size_t>(context_limit)){
            if(omitted+2<count){omitted+=2;continue;}return nullptr;
        }
        tokens.resize(-n);
        if(llama_tokenize(vocab,prompt.data(),prompt.size(),tokens.data(),tokens.size(),true,true)!=-n)return nullptr;
        break;
    }
    jclass cls=env->GetObjectClass(stream);
    jmethodID started=env->GetMethodID(cls,"onStart","(ZII)V"),token=env->GetMethodID(cls,"onToken","([B)V");
    env->DeleteLocalRef(cls);
    if(!started||!token||env->ExceptionCheck())return nullptr;
    size_t end=prompt.find_last_not_of(" \n\r\t");
    // Only a template-opened assistant suffix implies an initial reasoning
    // channel. A literal marker in a user's earlier message is not that suffix.
    bool thinking=end!=std::string::npos&&end>=6&&prompt.compare(end-6,7,"<think>")==0;
    env->CallVoidMethod(stream,started,static_cast<jboolean>(thinking),static_cast<jint>(tokens.size()),omitted);
    if(env->ExceptionCheck())return nullptr;
    llama_context_params cp=llama_context_default_params();
    cp.n_ctx=context_limit;cp.n_batch=512;cp.n_ubatch=256;cp.n_threads=4;cp.n_threads_batch=4;
    cp.abort_callback=[](void *){return cancel_generation.load();};
    llama_context *ctx=llama_init_from_model(model,cp);if(!ctx)return nullptr;
    llama_sampler *sampler=llama_sampler_chain_init(llama_sampler_chain_default_params());
    if(!sampler){llama_free(ctx);return nullptr;}
    llama_sampler_chain_add(sampler,llama_sampler_init_greedy());
    llama_batch_ext *batch=llama_batch_ext_init(ctx);
    if(!batch){llama_sampler_free(sampler);llama_free(ctx);return nullptr;}
    bool ok=true;int pos=0;
    for(int start=0;start<static_cast<int>(tokens.size());start+=256){
        if(cancel_generation.load()){ok=false;break;}
        int n=std::min(256,static_cast<int>(tokens.size())-start);
        batch_tokens(batch,tokens.data()+start,n,start);
        if(llama_process(ctx,LLAMA_PROCESS_TYPE_DECODE,batch)!=0){ok=false;break;}pos+=n;
    }
    std::string answer;
    for(int i=0;ok&&i<limit;i++){
        if(cancel_generation.load()){ok=false;break;}
        llama_token next=llama_sampler_sample(sampler,ctx,-1);
        if(llama_vocab_is_eog(vocab,next))break;
        std::vector<char> piece(1024);
        int n=llama_token_to_piece(vocab,next,piece.data(),piece.size(),0,true);
        if(n<0){piece.resize(-n);n=llama_token_to_piece(vocab,next,piece.data(),piece.size(),0,true);}
        if(n<0||n>65536||answer.size()+n>262144){ok=false;break;}
        answer.append(piece.data(),n);
        jbyteArray bytes=env->NewByteArray(n);if(!bytes){ok=false;break;}
        env->SetByteArrayRegion(bytes,0,n,reinterpret_cast<jbyte *>(piece.data()));
        env->CallVoidMethod(stream,token,bytes);env->DeleteLocalRef(bytes);
        if(env->ExceptionCheck()){ok=false;break;}
        batch_tokens(batch,&next,1,pos++);
        if(llama_process(ctx,LLAMA_PROCESS_TYPE_DECODE,batch)!=0){ok=false;break;}
    }
    llama_batch_ext_free(batch);llama_sampler_free(sampler);llama_free(ctx);
    if(!ok)return nullptr;
    jbyteArray bytes=env->NewByteArray(answer.size());
    if(bytes)env->SetByteArrayRegion(bytes,0,answer.size(),reinterpret_cast<const jbyte *>(answer.data()));
    return bytes;
}
