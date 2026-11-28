#pragma once
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

// The same actual local vision path is used by Android JNI and the host
// qualification executable. No filename-derived answer or simulated model.
struct VisionResult {
    std::string text;
    int prompt_tokens=0, generated_tokens=0;
    bool end_of_generation=false;
};
using VisionCancel=std::function<bool()>;
using VisionStart=std::function<bool(int)>;
using VisionPiece=std::function<bool(const char*,int)>;
bool run_native_vision(const std::string &model_path,const std::string &projector_path,
                       int width,int height,const std::vector<uint8_t>& rgb,
                       const std::string &question,int context_tokens,int output_tokens,int threads,
                       const VisionCancel &cancel,const VisionStart &start,const VisionPiece &piece,
                       VisionResult &out,std::string &error);
