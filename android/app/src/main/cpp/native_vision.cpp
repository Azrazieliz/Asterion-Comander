#include "native_vision.h"
#include "llama.h"
#include "ggml-backend.h"
#include "mtmd.h"
#include "mtmd-helper.h"
#include <algorithm>
#include <memory>

namespace {
template<class T,void(*Free)(T*)> using owned=std::unique_ptr<T,decltype(Free)>;
bool cancelled(void *data){return (*static_cast<const VisionCancel*>(data))();}
}
bool run_native_vision(const std::string &model_path,const std::string &projector_path,
                       int width,int height,const std::vector<uint8_t>& rgb,
                       const std::string &question,int context_tokens,int output_tokens,int threads,
                       const VisionCancel &cancel,const VisionStart &start,const VisionPiece &piece,
                       VisionResult &out,std::string &error) {
    auto fail=[&](const char *why){error=why;return false;};
    out=VisionResult{};
    if(width<1||height<1||width>1024||height>1024||
        rgb.size()!=static_cast<size_t>(width)*height*3||question.empty()||question.size()>8192||
        context_tokens<512||context_tokens>4096||output_tokens<1||output_tokens>1024||
        output_tokens+128>context_tokens||threads<1||threads>8)
        return fail("vision_input_invalid");
    if(cancel())return fail("vision_cancelled");
    // All allocations are local to this invocation; no simultaneous 7B text model.
    auto mp=llama_model_default_params();
    ggml_backend_dev_t cpu_only[]={nullptr};
    mp.devices=cpu_only;mp.n_gpu_layers=0;mp.load_mode=LLAMA_LOAD_MODE_MMAP;mp.use_extra_bufts=false;
    mp.progress_callback=[](float,void *data){return !cancelled(data);};
    mp.progress_callback_user_data=const_cast<VisionCancel*>(&cancel);
    owned<llama_model,llama_model_free> model(llama_model_load_from_file(model_path.c_str(),mp),llama_model_free);
    if(!model||cancel())return fail("vision_model_load_failed");
    auto vp=mtmd_context_params_default();
    vp.use_gpu=false;vp.device=nullptr;vp.print_timings=false;vp.warmup=false;vp.n_threads=threads;
    vp.progress_callback=[](float,void *data){return !cancelled(data);};
    vp.progress_callback_user_data=const_cast<VisionCancel*>(&cancel);
    owned<mtmd_context,mtmd_free> visual(mtmd_init_from_file(projector_path.c_str(),model.get(),vp),mtmd_free);
    if(!visual||!mtmd_support_vision(visual.get())||cancel())return fail("vision_projector_load_failed");
    owned<mtmd_bitmap,mtmd_bitmap_free> bitmap(mtmd_bitmap_init(width,height,rgb.data()),mtmd_bitmap_free);
    if(!bitmap)return fail("vision_bitmap_failed");
    const char *marker=mtmd_get_marker(visual.get());
    const char *tmpl=llama_model_chat_template(model.get(),nullptr);
    if(!marker||!*marker||!tmpl||question.find(marker)!=std::string::npos)
        return fail("vision_template_invalid");
    std::string user=std::string(marker)+"\n"+question;
    const char *system="Answer the question using the actual supplied image. Distinguish what is visible from uncertainty. Do not invent actions or claim independent verification.";
    llama_chat_message messages[]={{"system",system},{"user",user.c_str()}};
    std::vector<char> rendered(user.size()*3+4096);
    int size=llama_chat_apply_template(tmpl,messages,2,true,rendered.data(),rendered.size());
    if(size<1||static_cast<size_t>(size)>=rendered.size())return fail("vision_template_render_failed");
    std::string prompt(rendered.data(),size);
    mtmd_input_text input{prompt.c_str(),prompt.size(),true,true};
    const mtmd_bitmap *bitmaps[]={bitmap.get()};
    owned<mtmd_input_chunks,mtmd_input_chunks_free> chunks(mtmd_input_chunks_init(),mtmd_input_chunks_free);
    if(!chunks||mtmd_tokenize(visual.get(),chunks.get(),&input,bitmaps,1)!=0)
        return fail("vision_tokenization_failed");
    size_t tokens=mtmd_helper_get_n_tokens(chunks.get());
    llama_pos positions=mtmd_helper_get_n_pos(chunks.get());
    if(tokens==0||positions<=0||tokens+output_tokens+32>static_cast<size_t>(context_tokens)||
        static_cast<int64_t>(positions)+output_tokens+32>context_tokens)
        return fail("vision_context_budget_exceeded");
    out.prompt_tokens=static_cast<int>(tokens);
    if(cancel()||!start(out.prompt_tokens))return fail("vision_cancelled");
    auto cp=llama_context_default_params();
    cp.n_ctx=context_tokens;cp.n_batch=128;cp.n_ubatch=64;cp.n_threads=threads;cp.n_threads_batch=threads;
    cp.offload_kqv=false;cp.op_offload=false;
    cp.abort_callback=cancelled;cp.abort_callback_data=const_cast<VisionCancel*>(&cancel);
    owned<llama_context,llama_free> ctx(llama_init_from_model(model.get(),cp),llama_free);
    if(!ctx)return fail("vision_context_failed");
    llama_pos pos=0;
    // Evaluates actual image embeddings through the model; no OCR or text surrogate.
    if(mtmd_helper_eval_chunks(visual.get(),ctx.get(),chunks.get(),0,0,64,true,&pos)!=0||cancel())
        return fail("vision_prefill_failed");
    owned<llama_sampler,llama_sampler_free> sampler(llama_sampler_chain_init(llama_sampler_chain_default_params()),llama_sampler_free);
    if(!sampler)return fail("vision_sampler_failed");
    llama_sampler_chain_add(sampler.get(),llama_sampler_init_greedy());
    owned<llama_batch_ext,llama_batch_ext_free> batch(llama_batch_ext_init(ctx.get()),llama_batch_ext_free);
    if(!batch)return fail("vision_batch_failed");
    const llama_vocab *vocab=llama_model_get_vocab(model.get());
    for(int i=0;i<output_tokens;i++){
        if(cancel())return fail("vision_cancelled");
        llama_token token=llama_sampler_sample(sampler.get(),ctx.get(),-1);
        if(llama_vocab_is_eog(vocab,token)){out.end_of_generation=true;break;}
        std::vector<char> bytes(1024);
        int n=llama_token_to_piece(vocab,token,bytes.data(),bytes.size(),0,true);
        if(n<0){if(n< -65536)return fail("vision_piece_too_large");bytes.resize(-n);n=llama_token_to_piece(vocab,token,bytes.data(),bytes.size(),0,true);}
        if(n<0||n>65536||out.text.size()+n>262144)return fail("vision_output_budget");
        out.text.append(bytes.data(),n);out.generated_tokens++;
        if(!piece(bytes.data(),n))return fail("vision_stream_failed");
        if(i+1==output_tokens)break;
        llama_batch_ext_clear(batch.get());
        int at=llama_batch_ext_add_token(batch.get(),0,token);
        llama_batch_ext_set_pos(batch.get(),at,&pos);++pos;
        llama_batch_ext_set_output_logits(batch.get(),0,true);
        if(llama_process(ctx.get(),LLAMA_PROCESS_TYPE_DECODE,batch.get())!=0)return fail("vision_decode_failed");
    }
    return !out.text.empty()||fail("vision_empty_output");
}
