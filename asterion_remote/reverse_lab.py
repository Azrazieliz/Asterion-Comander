"""Offline-first static reverse engineering for EXTERNAL software with no source.

Opens a user-authorized binary and inspects real PE, ELF, DEX, ZIP/APK
structures. No execution, injection, security bypass, DRM removal or mutation
of the input. Android JADX/Ghidra dynamic workflows remain separate plugins.
The output is evidence from the actual bytes; not a reconstructed source tree.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import zipfile

_MAX_FILE=512*1024*1024
_MAX_ARCHIVE=4000
_MAX_MEM=8*1024*1024
_HASH_CHUNK=1024*1024
_BIN_NAMES={3:"x86",20:"PowerPC",40:"ARM",62:"x86_64",183:"aarch64",
            243:"RISC-V"}
_PE_ARCH={0x14c:"x86",0x8664:"x86_64",0x1c0:"ARM",0xaa64:"aarch64"}
_EXEC_EXT={".exe",".dll",".so",".dex",".jar",".apk",".ps1",".bat",".sh"}


def _sha_file(file:Path)->str:
    digest=hashlib.sha256()
    with file.open("rb") as stream:
        for buf in iter(lambda:stream.read(_HASH_CHUNK),b""):
            digest.update(buf)
    return digest.hexdigest()


def _pe(file:Path)->dict:
    with file.open("rb") as h:
        header=h.read(128)
        if len(header)<64 or header[:2]!=b"MZ":
            raise ValueError("pe_dos_header_invalid")
        coff=struct.unpack_from("<I",header,0x3c)[0]
        if coff<64 or coff>file.stat().st_size-24 or coff>_MAX_FILE-24:
            raise ValueError("pe_signature_offset_invalid")
        h.seek(coff)
        data=h.read(1024)
    if len(data)<24 or data[:4]!=b"PE\0\0":
        raise ValueError("pe_signature_missing")
    machine, sections, timestamp,_,_,options,flags=struct.unpack_from(
        "<HHIIIHH",data,4)
    if not 1<=sections<=96 or options>512:
        raise ValueError("pe_sections_invalid")
    magic=struct.unpack_from("<H",data,24)[0] if options>=2 else 0
    return {"type":"pe","architecture":_PE_ARCH.get(machine,hex(machine)),
            "sections":sections,"coff_timestamp":timestamp,
            "format":"PE32+" if magic==0x20b else
                     "PE32" if magic==0x10b else "unknown",
            "coff_characteristics":flags,
            "source_recovered":False}


def _elf(file:Path)->dict:
    with file.open("rb") as h:data=h.read(64)
    if len(data)<52 or data[:4]!=b"\x7fELF" or data[4] not in (1,2):
        raise ValueError("elf_header_invalid")
    if data[5] not in (1,2):
        raise ValueError("elf_endianness_invalid")
    endian="<" if data[5]==1 else ">"
    e_type,e_machine=struct.unpack_from(endian+"HH",data,16)
    return {"type":"elf","bitness":32 if data[4]==1 else 64,
            "endianness":"little" if endian=="<" else "big",
            "architecture":_BIN_NAMES.get(e_machine,hex(e_machine)),
            "elf_type":e_type,"source_recovered":False}


def _dex_bytes(data:bytes)->dict:
    if len(data)<112 or not data[:4]==b"dex\n" or data[7]!=0:
        raise ValueError("dex_header_invalid")
    version=data[4:7].decode("ascii","replace")
    if not version.isdigit():raise ValueError("dex_version_invalid")
    size,header_size,endian=struct.unpack_from("<III",data,32)
    if header_size!=112 or size>len(data) or size<112:
        raise ValueError("dex_size_or_header_invalid")
    if endian not in {0x12345678,0x78563412}:
        raise ValueError("dex_endianness_invalid")
    strings,types,protos,fields,methods,classes=[
        struct.unpack_from("<I",data,p)[0]
        for p in (56,64,72,80,88,96)]
    if any(n>10_000_000 for n in (strings,types,protos,fields,methods,classes)):
        raise ValueError("dex_table_counts_invalid")
    return {"type":"android_dex","dex_version":version,
            "declared_file_bytes":size,"string_ids":strings,
            "type_ids":types,"method_ids":methods,"field_ids":fields,
            "class_definitions":classes,
            "source_recovered":False}


def _archive(file:Path, *, apk:bool)->dict:
    with zipfile.ZipFile(file) as z:
        entries=z.infolist()
        if len(entries)>_MAX_ARCHIVE:
            raise ValueError("archive_inspection_entry_limit")
        names=set(x.filename for x in entries)
        if apk and "AndroidManifest.xml" not in names:
            raise ValueError("apk_manifest_missing")
        dex=[]
        for name in sorted(names):
            if re.fullmatch(r"classes([1-9][0-9]*)?\.dex",name):
                entry=z.getinfo(name)
                if entry.file_size>_MAX_MEM:
                    dex.append({"filename":name,"state":"large_dex_needs_jadx"})
                    continue
                try:meta=_dex_bytes(z.read(name))
                except (ValueError,RuntimeError,zipfile.BadZipFile):
                    meta={"type":"unknown_or_damaged_dex"}
                dex.append({"filename":name,**meta})
        signed=any(
            name.startswith("META-INF/") and
            name.upper().endswith((".RSA",".DSA",".EC"))
            for name in names)
        executable_entries=sum(Path(i.filename).suffix.lower() in _EXEC_EXT
                               for i in entries)
        total_unpacked=sum(x.file_size for x in entries)
        return {
            "type":"android_apk" if apk else "zip_container",
            "entries":len(entries),"unpacked_bytes_declared":total_unpacked,
            "contains_binary_executables":executable_entries>0,
            "executable_entries":executable_entries,
            "v1_certificate_container_present":signed,
            # APK V2/V3 signing is outside ZIP entries; absence here does NOT
            # mean unsigned. Full signature verification needs apksigner.
            "apk_signing_fully_verified":False,
            "android_dex":dex[:40],
            "android_manifest_present":"AndroidManifest.xml" in names,
            "source_recovered":False,
        }


def inspect(path:str|Path)->dict:
    file=Path(path).expanduser().resolve(strict=True)
    if not file.is_file() or not stat.S_ISREG(file.stat().st_mode):
        raise ValueError("regular_binary_file_required")
    size=file.stat().st_size
    if size<4 or size>_MAX_FILE:
        raise ValueError("binary_size_outside_inspection_budget")
    with file.open("rb") as h:head=h.read(128)
    if head.startswith(b"MZ"):meta=_pe(file)
    elif head.startswith(b"\x7fELF"):meta=_elf(file)
    elif head.startswith(b"dex\n"):meta=_dex_bytes(file.read_bytes()
                                                 if size<=_MAX_MEM else
                                                 head)
    elif head.startswith(b"PK\x03\x04"):
        meta=_archive(file,apk=file.suffix.lower()==".apk")
    else:
        meta={"type":"unrecognized",
              "recognized_format":False,"source_recovered":False}
    # File can change while being inspected; a digest of its final content
    # makes the report independently comparable, not proof of a stable file.
    stamp=file.stat()
    sha=_sha_file(file)
    if file.stat().st_size!=stamp.st_size:
        raise RuntimeError("inspected_binary_changed_during_hash")
    return {
        "ok":True,"bytes":size,"sha256":sha,
        "static_analysis_only":True,
        "input_file_modified":False,
        "format":meta,
        "full_source_decompiled":False,
        "live_process_instrumented":False,
        "requires_authorized_binary":True,
        "source_path_disclosed":False,
    }
