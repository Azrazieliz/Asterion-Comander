"""Structural, non-device regressions for signed native inference profiles.

These checks do not claim inference, reasoning quality or an installed Android release.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "android/app/src/main/cpp/on_device_llm.cpp"
JAVA = ROOT / "android/app/src/main/java/com/asterion/control"
MANIFEST = ROOT / "android/app/src/main/assets/models/control-model.json"


def test_model_profile_has_signed_asset_hash_and_reasonable_budgets():
    profile = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert profile["file"].endswith(".gguf")
    assert profile["bytes"] > 1_000_000
    assert len(profile["sha256"]) == 64
    assert profile["max_input_chars"] > 1800
    assert profile["max_new_tokens"] > 192
    assert profile["context_tokens"] >= profile["max_new_tokens"] + 256
    assert "chat_format" not in profile  # native backend selects GGUF template
    assert len(profile["system_text"]) > 40
    assert "/no_think" not in profile["system_text"]
    assert "cannot autonomously operate" not in profile["system_text"].lower()


def test_on_device_loader_uses_profile_not_named_vendor_constants():
    source = (JAVA / "OnDeviceLlm.java").read_text(encoding="utf-8")
    assert "OnDeviceModelProfile.read(context)" in source
    assert "profile.systemInstructions(guidance)" in source
    assert "nativeGenerate(systemText.getBytes(StandardCharsets.UTF_8),roles,content," in source
    assert "ControlAssistantPreferences.promptGuidance(context)" in source
    assert "ControlAssistantPreferences.outputTokens(context,profile)" in source
    assert "outputBudget,contextBudget" in source
    assert "sha.equals(hex(digest.digest()))" in source
    assert "GATE.begin(request)" in source
    assert "GATE.end(request)" in source
    assert "/no_think" not in source
    assert "MODEL_FILE=" not in source
    assert "Qwen3-0.6B" not in source


def test_jni_preserves_cancellation_and_rejects_context_overflow():
    code = NATIVE.read_text(encoding="utf-8")
    assert "jint context_limit" in code
    assert "jbyteArray jsystem,jobjectArray jroles,jobjectArray jcontent" in code
    assert "llama_model_chat_template(model,nullptr)" in code
    assert "llama_chat_apply_template(chatTemplate,messages.data(),messages.size(),true" in code
    assert "limit>2048" in code
    assert "if(bytes>262144)" in code
    assert "static_cast<size_t>(-n)+static_cast<size_t>(limit)+32u" in code
    assert "cp.n_ctx=context_limit;" in code
    assert "cancel_generation.load" in code
    assert "load_profile(value,nullptr,nullptr,0,false)" in code  # unsigned callers cannot select an accelerator


def test_jobs_keep_durable_receipt_before_work_and_use_profile_budget():
    source = (JAVA / "OnDeviceAiJobs.java").read_text(encoding="utf-8")
    assert "OnDeviceModelProfile.read(ctx).inputChars" in source
    assert "prompt.length()>maxInputChars" in source
    assert "persist(ctx,job);" in source
    assert "EXECUTOR.submit(()->execute(app,job,prompt));" in source
    assert "OnDeviceLlm.generate(ctx,prompt,job.request)" in source
    assert "previous_process_outcome_unavailable" in source


def test_owner_settings_are_local_and_not_tool_permissions():
    policy=(JAVA/"ControlAssistantPreferences.java").read_text(encoding="utf8")
    view=(JAVA/"MainActivity.java").read_text(encoding="utf8")
    assert "MODE_PRIVATE" in policy
    assert "guidance.length()>2000" in policy
    assert "outputTokens" in policy
    assert "authorization and security controls" in policy
    assert "showPhoneAiPreferences" in view
    assert "ControlAssistantPreferences.save" in view


def test_encrypted_memory_contract_and_owner_review_controls():
    code=(JAVA/"ControlAssistantMemory.java").read_text(encoding="utf8")
    ui=(JAVA/"MainActivity.java").read_text(encoding="utf8")
    model=(JAVA/"OnDeviceLlm.java").read_text(encoding="utf8")
    assert 'KeyStore.getInstance("AndroidKeyStore")' in code
    assert 'AES/GCM/NoPadding' in code
    assert 'setKeySize(256)' in code
    assert 'if(!explicitlyOwnerApproved)' in code
    assert 'db.delete("memory","id=?",new String[]{id})' in code
    assert 'SELECT id,project,origin,nonce,payload' in code
    assert "ControlAssistantMemory.relevant(context,userPrompt,project)" in model
    assert "ControlAssistantMemory.remember" in ui
    assert "ControlAssistantMemory.recent" in ui
    assert "ControlAssistantMemory.forget" in ui
    assert "new AlertDialog.Builder(this)" in ui


def test_workspace_uses_existing_encrypted_store_and_retains_failed_turns():
    prefs=(JAVA/"ControlAssistantPreferences.java").read_text(encoding="utf8")
    view=(JAVA/"MainActivity.java").read_text(encoding="utf8")
    workspace=(JAVA/"AssistantActivity.java").read_text(encoding="utf8")
    session=(JAVA/"AssistantSession.java").read_text(encoding="utf8")
    memory=(JAVA/"ControlAssistantMemory.java").read_text(encoding="utf8")
    assert "encrypted_local_chat_history_enabled" in prefs
    assert "keepHistory.isChecked()" in view
    assert "new Intent(this,AssistantActivity.class)" in view
    assert "Ask Asterion · on this phone" not in view
    assert "response does not execute app commands" not in view
    assert "ControlAssistantMemory.saveConversation" in session
    assert "response incomplete" in workspace
    assert "cipher.updateAAD(conversation.id" in memory
    assert 'CREATE TABLE IF NOT EXISTS conversation' in memory
    assert 'super(c,DB,null,3)' in memory
    assert 'if(oldVersion==1&&newVersion<=3){createConversations(db);oldVersion=2;}' in memory
    assert 'if(oldVersion==2&&newVersion==3){createProjectSources(db);return;}' in memory
    assert "session.conversation.fork()" in workspace


def test_vulkan_selection_is_real_and_signed_bounded():
    profile=(JAVA/"OnDeviceModelProfile.java").read_text(encoding="utf-8")
    prefs=(JAVA/"ControlAssistantPreferences.java").read_text(encoding="utf-8")
    native=NATIVE.read_text(encoding="utf-8")
    llm=(JAVA/"OnDeviceLlm.java").read_text(encoding="utf-8")
    assert 'vulkan_max_layers' in profile and 'invalid_mutable_vulkan_budget' in profile
    assert 'vulkan_layers_"+profile.sha256' in prefs
    assert 'layers>profile.maxVulkanLayers' in llm
    assert 'nativeVulkanProbe()' in llm and 'if(!passed)return probe.put("selection_saved",false)' in llm
    assert 'ggml_backend_dev_init(device,nullptr)' in native
    assert 'ggml_backend_graph_compute(backend.get(),graph)' in native
    assert 'ggml_backend_tensor_get(c,output.data()' in native
    assert 'max_error>0.0001f' in native
    assert 'params.devices=devices' in native
    assert 'params.load_mode=LLAMA_LOAD_MODE_MMAP' in native
    assert 'params.use_extra_bufts=false' in native
    assert 'gpu_execution_verified",false' in llm
    assert 'model_gpu_inference_verified",false' in llm


def test_local_tool_feedback_and_pressure_guard_are_on_actual_generation_path():
    llm=(JAVA/"OnDeviceLlm.java").read_text(encoding="utf-8")
    guard=(JAVA/"InferenceResourceGuard.java").read_text(encoding="utf-8")
    assert 'resourceGuard=new InferenceResourceGuard(context,GATE,request)' in llm
    assert 'gate.abortActive(request)' in guard
    assert 'sample.memory.lowMemory' in guard
    assert 'THERMAL_STATUS_SEVERE' in guard
    assert 'resourceGuard.check();' in llm
    assert 'AssistantCalculator.evaluate(result)' in llm
    assert 'nextSystem=systemText+"\\n"+calculation.reference()' in llm
    assert 'nativeGenerate(nextSystem.getBytes(StandardCharsets.UTF_8)' in llm
    assert 'tool_reasoning_passes' in llm
    assert 'resourceGuard.close()' in llm
