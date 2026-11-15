"""Compile and test the pure-Java IP observer, no APK/build/phone/network.

Fetch exact Git ref and run this on existing owner Windows development machine.
The script itself never connects to public IP observers and never changes VPN.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCES=(
    "android/app/src/main/java/com/asterion/control/PublicExitIp.java",
    "android/app/src/test/java/com/asterion/control/PublicExitIpCheck.java",
)


def _find(name:str)->str|None:
    available=shutil.which(name)
    if available:return available
    for key in ("JAVA_HOME","JDK_HOME","GRADLE_JAVA_HOME"):
        base=os.getenv(key,"")
        if base:
            p=Path(base)/"bin"/(name+".exe" if os.name=="nt" else name)
            if p.is_file():return str(p)
    for root in (
        "C:/Program Files/Android/Android Studio/jbr/bin",
        "C:/Program Files/Java",
    ):
        path=Path(root)
        if not path.exists():continue
        direct=path/(name+".exe")
        if direct.is_file():return str(direct)
        for sub in path.glob("jdk*/bin"):
            possible=sub/(name+".exe")
            if possible.is_file():return str(possible)
    return None


def main(repo:str,ref:str="FETCH_HEAD")->int:
    javac=_find("javac")
    java=_find("java")
    if not javac or not java:
        print("JAVA_SOURCE_NOT_COMPILED: JDK toolchain unavailable")
        return 12
    with tempfile.TemporaryDirectory(prefix="asterion_exit_ip_java_") as folder:
        base=Path(folder)
        source_files=[]
        for name in SOURCES:
            data=subprocess.check_output([
                "git","-C",repo,"show",ref+":"+name],timeout=15)
            target=base/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            source_files.append(str(target))
        classes=base/"classes"
        classes.mkdir()
        compiled=subprocess.run(
            [javac,"-encoding","UTF-8","-d",str(classes),*source_files],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,timeout=40)
        print("JAVA_COMPILATION_EXIT",compiled.returncode)
        if compiled.returncode:
            print(compiled.stderr[-2200:])
            return 13
        result=subprocess.run(
            [java,"-cp",str(classes),
             "com.asterion.control.PublicExitIpCheck"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,timeout=20)
        print("JAVA_UNIT_EXIT",result.returncode)
        print(result.stdout[-1200:])
        if result.returncode:print(result.stderr[-1600:])
        return 0 if result.returncode==0 else 14


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: verify_java_public_exit_isolated.py <repo>")
    raise SystemExit(main(sys.argv[1]))
