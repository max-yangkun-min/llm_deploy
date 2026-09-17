from pathlib import Path


path = Path("/opt/vllm/setup.py")
text = path.read_text(encoding="utf-8")
start_marker = "ext_modules = []\n"
end_marker = "package_data = {\n"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("could not locate setup.py extension block")

replacement = '''ext_modules = []

# This image targets A100 sm_80 only. Keep the extensions required by the
# GLM-5.2 AWQ path and omit Hopper/Blackwell-only native components.
if _is_cuda():
    ext_modules.append(CMakeExtension(name="vllm.cumem_allocator"))
    ext_modules.append(CMakeExtension(name="vllm.triton_kernels", optional=True))
    ext_modules.append(CMakeExtension(name="vllm.vllm_flash_attn._vllm_fa2_C"))
    if sys.version_info >= (3, 11):
        ext_modules.append(CMakeExtension(name="vllm.spinloop"))
    ext_modules.append(CMakeExtension(name="vllm._C_stable_libtorch"))
    ext_modules.append(CMakeExtension(name="vllm._moe_C_stable_libtorch"))

'''

path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print("setup.py patched for sm_80-only native build")
