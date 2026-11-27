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
                    str(JAVA/'AssistantStructured.java'),
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
