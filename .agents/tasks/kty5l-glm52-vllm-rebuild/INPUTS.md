# kty5l GLM-5.2 rebuild inputs

Persistent on-site feedback screenshots:

- `kty5l/36d5df69885a638c351cba9535c61ee4.jpg`
  - Size: 947669 bytes
  - SHA-256: `1f9b635b5402a2c90d9ee4ef06f76b9f9b32bdbf085cf30789b6d7c29732028c`
  - Purpose: latest runtime failure; kernel uvicorn/python3.11 segfault and
    Docker exit state, plus GLM-5.2-AWQ-INT4 shard listing.
- `kty5l/790892acf0d6734bd645639916a14048.jpg`
  - Size: 663192 bytes
  - SHA-256: `83023b8f90de9cf97c58681489ab3647f5a9b0a692f64cf86c79d0c88d5ad58d`
  - Purpose: checksum check after CRLF normalization; README and run.sh differ.
- `kty5l/942872f0d41a76a7518c6d4ad871e637.jpg`
  - Size: 1125971 bytes
  - SHA-256: `99cc700419cffd21763695b6fa7750842b830ec6ac82374b46d7f6f862f37d2c`
  - Purpose: original manifest verification failing because CR characters are
    embedded in recorded paths.

No text log from immediately before the segfault has been provided.

Vendored build source added during the clean-v2 retry:

- `kty5l/build-glm52-vllm-cu128/vendor-sources/cutlass-v4.4.2-da5e086.tar.gz`
  - Size: 39415196 bytes
  - SHA-256: `fc0d4b8aa08cb2d973f06cbc294099899da881f86a4cb93e39e8e6d8fe7d85bd`
  - Purpose: offline CUTLASS `v4.4.2` source for native vLLM compilation.
  - Source: verified domestic GitCode tag `v4.4.2`, commit
    `da5e086dab31d63815acafdac9a9c5893b1c69e2`.
