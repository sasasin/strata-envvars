# `STRATA_INK_EXACT_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

AMD HIP 版 `strata-inkling` backend で、speculative verify の複数行計算に one-token step と同じ row 計算経路を使うかを制御する。既定では有効で、`0` から始まる値を設定すると無効になる。これは一般の batch 全体を常時切り替える設定ではなく、単一 slot の chain verify または tree verify の処理中に限って有効になる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:739,3489-3502,5061-5065,5830-5833`）。

## 値と判定

backend の `init()` が `std::getenv` で取得し、環境変数が設定されていれば `ev[0] == '0'` だけを判定する。文字列全体の比較、数値変換、空白除去、大文字小文字変換はない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-568,739`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP backend の初期化 | `exact_verify_enabled_` は `true` のまま | 空文字、`1`、`true`、`false`、空白始まりの値など、先頭文字が `0` 以外 | `0`、`0anything`、`0 ` など、先頭文字が `0` |

`false` も先頭が `f` のため有効扱いであり、`0.0` なども無効扱いになる。文字列や数値としての妥当性検査はしない。明示的に空文字を渡す場合も先頭文字は終端文字 `\0` であり、無効条件の `'0'` とは一致しないため有効になる（同上）。CLI 引数や設定ファイルによる上書き、別の環境変数との優先順位はこの設定の実読み取り経路にはない。

## 有効になる条件

- `strata-inkling` が HIP backend を含む構成であること。inkling CMake は `STRATA_ENABLE_HIP` が有効な場合に HIP backend サブディレクトリを追加し、同 backend は `ink_hip_backend.hip.cpp` を HIP ソースとしてビルドする（`engine/src/inkling2/CMakeLists.txt:237-242`、`engine/src/inkling2/hip/CMakeLists.txt:30-32`）。したがって CUDA・CPU 等の別 backend ではこの読み取りコードは使われない。
- 値が有効であっても、通常の単一行 decode では `exact_rows_` は有効化されない。chain verify では batch が 2〜8 行で、同一 slot の snapshot があり、位置が連続するときだけ `rec_slot` が設定され、その場合に環境設定を反映する scope が有効になる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3489-3502`）。
- tree verify では `forward_tree_verify` の処理中に環境設定を反映する。関数は `B` が 1〜12 の範囲外なら処理せず戻る（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:5061-5065`）。
- tree verify 内の exact split-KV attention 経路は `!is_fp8` の場合に限られる。FP8 KV の場合はこの exact attention 分岐に入らない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:5390-5405`）。

## 実行時の詳細

backend インスタンスの `init()` 中に一度読み、`exact_verify_enabled_` に保存する。したがって同じ backend インスタンスの稼働中に環境を書き換えても反映されず、再初期化時には改めて読み取る（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-568,739`）。chain/tree verify の scope は開始時に `exact_rows_` の以前の値を保存し、終了時に戻す（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3502,5062-5065,5855-5859`）。

有効な scope 内では `launch_bf16_opt` が行数 `M=2..16` の BF16 線形計算を `launch_bf16_rows_exact` に送る（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2918-2923`）。また attention sink projection や attention kernel、loop controller、MoE router/expert の経路選択にも `exact_rows_` が使われ、verify 行で one-token 相当の計算経路を選ぶ（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3790-3809,3943-3949,4043-4048,4145-4157,4230-4240,5390-5403,5453-5467`）。ソースコメントはこの設定を切ると exact-row 経路が無効になると記す（同ファイル `:5830-5833`）。これらは計算経路を変える実装上の根拠であり、出力の同一性や性能差をこの調査で実測したものではない。

## ログと測定値

この変数の値を理由として出す専用ログ、警告、終了・失敗経路は見つからなかった。設定値に応じて verify 時に計算経路が変わるが、その選択自体はログに出力されない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:739,2918-2923,3502,5062-5065`）。この変数に関する条件付き測定値も、参照したソースと `docs/SETTINGS.md:397` には記載されていない。

## 根拠

- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-568,739` — 初期化時の読み取りと既定値
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2918-2923,3489-3502,5061-5065,5855-5859` — linear dispatch と verify scope
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3790-3809,3943-3949,4043-4048,4145-4157,4230-4240,5390-5405,5453-5467` — scope 内で変わる計算経路と条件
- `engine/src/inkling2/CMakeLists.txt:237-242`、`engine/src/inkling2/hip/CMakeLists.txt:30-32` — HIP backend のビルド条件とソース
- `docs/SETTINGS.md:397` — 変数を AMD の on/off 項目として掲載（実際の値判定は上記ソースを根拠とする）
