"""Execute production Java presentation/state logic, without Android or an inference surrogate."""
from pathlib import Path
import os
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
    subprocess.run([compiler,'-d',str(tmp_path),str(JAVA/'AssistantOutput.java'),
                    str(JAVA/'AssistantConversation.java'),
                    str(ROOT/'tests/java/com/asterion/control/AssistantWorkspaceTest.java')],
                   check=True,capture_output=True,text=True)
    result=subprocess.run([runtime,'-cp',str(tmp_path),'com.asterion.control.AssistantWorkspaceTest'],
                          check=True,capture_output=True,text=True,timeout=30)
    assert '523 assistant output and conversation behavior assertions passed' in result.stdout
