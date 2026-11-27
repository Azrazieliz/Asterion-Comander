"""Execute production Java presentation/state logic, without Android or an inference surrogate."""
from pathlib import Path
import re
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'android/app/src/main/java/com/asterion/control'

def test_executable_split_utf8_reasoning_and_conversation_regressions(tmp_path):
    compiler=shutil.which('javac')
    runtime=shutil.which('java')
    if not compiler or not runtime:
        pytest.skip('JDK required for executable Java behavior tests')
    subprocess.run([compiler,'-encoding','UTF-8','-d',str(tmp_path),str(JAVA/'AssistantOutput.java'),
                    str(JAVA/'AssistantConversation.java'),str(JAVA/'AssistantActionRecord.java'),str(JAVA/'InferenceGate.java'),
                    str(ROOT/'tests/java/com/asterion/control/AssistantWorkspaceTest.java')],
                   check=True,capture_output=True,text=True)
    result=subprocess.run([runtime,'-cp',str(tmp_path),'com.asterion.control.AssistantWorkspaceTest'],
                          check=True,capture_output=True,text=True,timeout=30)
    match = re.fullmatch(r"(\d+) assistant output and conversation behavior assertions passed; no model/device acceptance claimed", result.stdout.strip())
    assert match, result.stdout
    assert int(match.group(1)) >= 548

def test_native_structured_response_data(tmp_path):
    compiler=shutil.which('javac')
    runtime=shutil.which('java')
    if not compiler or not runtime:
        pytest.skip('JDK required for executable Java behavior tests')
    subprocess.run([compiler,'-encoding','UTF-8','-d',str(tmp_path),
                    str(JAVA/'AssistantStructured.java'),str(JAVA/'AssistantArtifact.java'),
                    str(ROOT/'tests/java/com/asterion/control/AssistantStructuredTest.java')],
                   check=True,capture_output=True,text=True)
    result=subprocess.run([runtime,'-cp',str(tmp_path),'com.asterion.control.AssistantStructuredTest'],
                          check=True,capture_output=True,text=True,timeout=30)
    assert re.fullmatch(r"\d+ structured response assertions passed",result.stdout.strip())

def test_native_context_pack_reserves_output_and_preserves_full_reference_blocks(tmp_path):
    compiler=shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        pytest.skip('C++ compiler required for executable context packing tests')
    exe=tmp_path/('context-pack.exe' if __import__('os').name=='nt' else 'context-pack')
    subprocess.run([compiler,'-std=c++17','-I',str(ROOT/'android/app/src/main/cpp'),
                    str(ROOT/'tests/native/context_pack_test.cpp'),'-o',str(exe)],
                   check=True,capture_output=True,text=True)
    result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=10)
    assert 'Context pack behavior passed' in result.stdout

def test_memory_search_recovers_old_and_late_exact_passages(tmp_path):
    compiler=shutil.which('javac')
    runtime=shutil.which('java')
    if not compiler or not runtime:
        pytest.skip('JDK required for executable Java memory search tests')
    subprocess.run([compiler,'-encoding','UTF-8','-d',str(tmp_path),
                    str(JAVA/'AssistantMemorySearch.java'),
                    str(ROOT/'tests/java/com/asterion/control/AssistantMemorySearchTest.java')],
                   check=True,capture_output=True,text=True)
    result=subprocess.run([runtime,'-cp',str(tmp_path),'com.asterion.control.AssistantMemorySearchTest'],
                          check=True,capture_output=True,text=True,timeout=30)
    assert 'Memory search behavior passed' in result.stdout

def test_native_schedule_plan_and_no_catchup(tmp_path):
    compiler=shutil.which('javac')
    runtime=shutil.which('java')
    if not compiler or not runtime:
        pytest.skip('JDK required')
    subprocess.run([compiler,'-encoding','UTF-8','-d',str(tmp_path),
                    str(JAVA/'AssistantStructured.java'),str(JAVA/'AssistantSchedulePlan.java'),
                    str(ROOT/'tests/java/com/asterion/control/AssistantSchedulePlanTest.java')],
                   check=True,capture_output=True,text=True)
    result=subprocess.run([runtime,'-cp',str(tmp_path),'com.asterion.control.AssistantSchedulePlanTest'],
                          check=True,capture_output=True,text=True,timeout=30)
    assert 'Schedule plan behavior passed' in result.stdout

def test_local_schedule_reserves_before_dispatch_and_reuses_native_queue():
    code=(JAVA/'AssistantSchedules.java').read_text(encoding='utf-8')
    assert code.index('commit(c,a);\n            if(r.getString("kind").equals("reminder"))')<code.index('OnDeviceAiJobs.submit(c,')
    assert 'OnDeviceAiJobs.status(c,' in code and 'OnDeviceAiJobs.cancel(c,' in code
    assert 'if(!AgentService.running)return;' in code
    assert 'No automatic replay' in code
    assert 'AssistantSchedules.tick(this)' in (JAVA/'AgentService.java').read_text(encoding='utf-8')
    assert 'SCHEDULE_AAD' in (JAVA/'ControlAssistantMemory.java').read_text(encoding='utf-8')


def test_history_retrieval_is_project_scoped_source_linked_and_local_only():
    memory=(JAVA/'ControlAssistantMemory.java').read_text(encoding='utf-8')
    llm=(JAVA/'OnDeviceLlm.java').read_text(encoding='utf-8')
    prefs=(JAVA/'ControlAssistantPreferences.java').read_text(encoding='utf-8')
    assert 'if(!project.equals(saved.getString("project")))continue;' in memory
    assert 'search.add(id+"/"+mid,project,"Historical "+role' in memory
    assert '!seen.add(mid)' in memory and 'active)seen.add(m.id)' in memory
    assert 'scan coverage: ' in memory and 'bounded/partial' in memory
    assert 'if(listener!=null&&ControlAssistantPreferences.reuseHistory(context))' in llm
    assert 'return saveHistory(ctx)&&prefs(ctx).getBoolean(REUSE_HISTORY,true)' in prefs
    assert 'LIMIT ? OFFSET ?' in memory
    assert 'historyPage(offset+50)' in (JAVA/'AssistantActivity.java').read_text(encoding='utf-8')
