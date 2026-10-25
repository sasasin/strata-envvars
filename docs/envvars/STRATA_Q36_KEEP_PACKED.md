# `STRATA_Q36_KEEP_PACKED`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。作業開始時の Strata 作業ツリーは clean。対象は Strata 所有ソースであり、外部ライブラリの挙動は含めない。

## 役割

Qwen 3.5 (`strata-q36`) の expert 配置時に、ロード済みの packed Q8_0 decode copy を VRAM から解放する自動判断を抑止する。packed copy を維持したぶん routed expert が VRAM に収まりにくくなり、expert 配置は hybrid 経路を選ぶ可能性がある。変数は packed copy を新たに作る設定ではなく、その解放判断だけに関与する。

## 値と判定

値の parse は行わず、`std::getenv("STRATA_Q36_KEEP_PACKED") != nullptr` で設定有無を判定する。

| 状態 | 解放判断への効果 |
|---|---|
| unset | 他の条件も満たす場合、packed copy を解放できる |
| 設定あり（空文字を含む） | packed copy を解放しない。この判定では値の内容を問わない |

したがって `1` は慣例的な設定例にすぎず、`0`、`false`、空文字も「設定あり」として解放を抑止する。大文字小文字、数値、前後の空白は検査されない。

## 有効になる条件

この判断が実行されるのは `place_experts()` 内で、すべての条件を満たす場合に限る。

- `--expert-slots` が未指定相当（`slots <= 0`）。
- `--expert-vram` が明示されていない（`vram_gib < 0`）。
- routed expert 全体の必要量 `total` が、予約量を差し引いた現在の VRAM budget を超える。
- 解放可能な packed copy が少なくとも一つある（`packed_bytes > 0`）。
- packed copy を解放すると、expert 全体が budget 内に収まるか、MTP CPU 配置を許す条件下で main layers が budget と slack 内に収まる。

これらの条件のいずれかを満たさなければ、この環境変数の有無による解放判断は行われない。環境変数が設定されていても VRAM に余裕がある場合の expert 配置を強制変更するものではない。

## 実行時の詳細

Qwen 3.5 の loader は、`STRATA_Q8_PACKED` が有効で、Q8_0 行列の形状が eligible の場合に Q8_0 decode 用の packed copy を VRAM に作り、元の GGUF weight pointer と対応づけて `m.packed` に記録する。`place_experts()` はこの copy 群の総バイト数を計算し、上記の VRAM 条件に当たるときだけ `STRATA_Q36_KEEP_PACKED` を確認する。

変数が unset なら、各 copy の registry 登録を解除して VRAM を解放し、`m.packed` を空にして decode graph を reset する。その後、解放後の空き VRAM を使って expert を配置し、成功すると stderr に `strata-q36: the packed Q8_0 decode copies (...) given back so that every routed expert fits in VRAM ...` のログを出す。変数が設定されている場合はこの解放処理とログを通らず、保持した copy を含む現在の VRAM 状態で配置を続ける。hybrid expert pool を含まない build で expert が収まらない場合は、後続の配置処理がエラーを返し、`strata-q36` は stderr に理由を出して終了コード 1 で戻る。

この環境変数は `place_experts()` が呼ばれるたびに評価され、static cache ではない。`strata::qwen35::run()` は model load 後、engine 初期化の後に配置関数を呼び出す。Q8_0 packed copy 自体の作成有無は別の `STRATA_Q8_PACKED` 判定に依存し、Q36 の CUDA ソースでは非 Windows 時にその変数を未設定なら `1` として設定する。copy がないと `packed_bytes > 0` 条件を満たさず、この変数の配置判断への作用はない。

ソースコメントは、packed copy を解放すると routed experts が収まる例として「32 GB の UD-Q6_K_XL」を挙げる。また解放後の decode は GGUF layout を読む経路で bitwise に同じ出力だが少し遅いと説明している。これは実装コメントに記された設計・性能上の説明であり、この調査で実行測定した結果ではない。関連する詳細資料にこの環境変数の追加説明は見つからなかった。

## 根拠

- `src/qwen35/q36_engine.cu:891-919` — 行列ロード時の Q8_0 packed copy 作成と `m.packed` 登録。
- `src/qwen35/q36_engine.cu:1930-1977` — expert VRAM budget、解放条件、設定有無判定、unregister/free、graph reset とログ。
- `src/qwen35/q36_engine.cu:2019-2024` — CPU expert pool を持たない build で収まらない場合のエラー。
- `src/qwen35/q36_engine.cu:2404-2410,2414-2445` — `STRATA_Q8_PACKED` の非 Windows 未設定時の既定設定と、load 後に `place_experts()` を呼ぶ順序。
- `src/kernels/cuda/native_mmvq.cu:1990-2001` — 関連変数 `STRATA_Q8_PACKED` の文字列全体比較と eligible shape 条件。
