# kty5l on-site GPU-memory incident inputs

Last updated: 2026-07-27 21:44 (Asia/Shanghai)

| Path | Size (bytes) | SHA-256 | Purpose |
|---|---:|---|---|
| `kty5l/60670384ea8a03fda19393f7208c114d.jpg` | 562665 | `f60dfd193f21e5ec59ba8b02cbe0be4df07913d85c6f3e62611f1c36a1db3068` | Worker failure; `cuda:7` free-memory exception |
| `kty5l/781b08b8bcbfdd852d6bd2d2b8ab7351.jpg` | 754071 | `5207e867ae6375ff4514a0db30377293e1952bc87edfa44333495faac501c781` | `cuda:6` free-memory exception and partial model loading |
| `kty5l/e8a7629f99602d08a06f64a4c7af8c79.jpg` | 489693 | `e922e006ea9599aa3b50420432367fdd22328b32bc3afb2f6f91f6a2540203f` | Downstream segfault stack |
| `kty5l/ed08e9974fa2344250fe7a91c8543a27.jpg` | 669995 | `ee52f3fb96f123bc9c419c4aacf975aaa54793f4b17f1eb6d62576596444cda0` | Downstream engine failure stack |
| `kty5l/c7d6b8006f4efae32dd5d428c1b90ca1.jpg` | 818119 | `fd64a14b75278098af6cf80ea41698798d5592b19a70fbcf5254f31d659032f6` | Final API-server engine initialization failure |
| `kty5l/feb132e0f51c68e570d6d9fab4c59e67.jpg` | 737870 | `212fbe6b7b970f7f771111b261b85ef4b040c0809716253c3c99f849fd503bd8` | Retry: downstream `EngineCore failed to start` traceback |
| `kty5l/046b8ef4caba5ba092ea42c3bfd693f2.jpg` | 778732 | `16c28d08dfe7aed0f1b7b02d3400117e082a9a981a750d22ca7d36b844aab338` | Retry: downstream worker/API-server traceback |
| `kty5l/41ec773106299ce02a44df06cee232ea.jpg` | 727330 | `e722fbca661343296ac2ec1ca2740871257f81d0c9744ac74bc7edefb216b889` | Retry: final engine-core initialization failure |
| `kty5l/b393a9aa1c114c4ef6d08cbdbf40123d.jpg` | 812664 | `ee86e4dc679550cc76841cda663ac71790ca0874ee9e9838d9304b405f7396d6` | Retry root cause: `cuda:6` only 49.84 GiB free versus 71.33 GiB required |
| `kty5l/8e615cd22c4a9b51d81e751de30a0b06.jpg` | 920642 | `20b41dd711c512ed4d51813dbb580257c7cb2cb0392aa03f4f433129b22b8293` | Post-cleanup retry: downstream EngineCore/WorkerProc traceback only |
| `kty5l/38ba9028d30774cf282e0c0af0b8386c.jpg` | 959118 | `3ad27b56fdead718b9752ca69abda7bc30cdf9085f5762e8472d2e4ceff8acc1` | Post-cleanup retry: final API-server engine initialization failure only |
| `kty5l/f728f9169d7ee96355fae8dc731c55d9.jpg` | 1139221 | `566ec76d2c99c6647855bf360b88c81af3644d358aa531b63091a775fef1f463` | Post-cleanup startup: API config and expected missing-Qutlass warnings |
| `kty5l/7cdc6a27710b2a8716c9d0630d0b9bdb.jpg` | 1143931 | `756d0944c227253c6ad78d8e3b3befb7a0720bc2a93bd629846e3d5e4c5ab73a` | Post-cleanup startup: NCCL ranks 0-2 initialize |
| `kty5l/db90f32fed8cdf379eb7e2ea8f96e22c.jpg` | 1232644 | `2796c3e4c4908850e23a8205c458cb30749e096101cd5dacfbd0d630e1b1dbad` | Post-cleanup startup: ranks through 7 and expected platform fallbacks |
| `kty5l/89ceb42bc87377b0b8c59cbccde7192c.jpg` | 1134756 | `ed833c419e81afc4a1b10013ce483376a256c516b0d567050214ea6f1d38235b` | First actionable post-cleanup failure: TP0 native segfault at model-load start |
| `kty5l/36d5df69885a638c351cba9535c61ee4.jpg` | 947669 | `1f9b635b5402a2c90d9ee4ef06f76b9f9b32bdbf085cf30789b6d7c29732028c` | Kernel/user-space segfault evidence; container ExitCode 1 and OOMKilled false |
| `kty5l/942872f0d41a76a7518c6d4ad871e637.jpg` | 1125971 | `99cc700419cffd21763695b6fa7750842b830ec6ac82374b46d7f6f862f37d2c` | Manifest verification fails because CRLF adds literal carriage returns to every listed path |
| `kty5l/790892acf0d6734bd645639916a14048.jpg` | 663192 | `83023b8f90de9cf97c58681489ab3647f5a9b0a692f64cf86c79d0c88d5ad58d` | Completed normalized manifest check: only README.md and scripts/run.sh mismatch; all model/image artifacts pass |
