from cartograph.indexer import code_files
files = code_files("data/repos/Irfan240305__OmniReserve")
print(len(files))
for f in files[:20]:
    print(f)