# `STRATA_QSA_STAT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `main...origin/main` で変更なし。

## 役割

HIP の QSA prompt-attention WMMA 実装で、連続 query の選択 cell がどの程度重複するかを診断し、行 union による共有効果の目安を stderr に出します。attention の選択や計算方法を切り替える変数ではありません。CUDA ビルドではこの診断コードは `__HIPCC__` ガード内の WMMA 実装に含まれず、読み取り箇所もありません。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |

値の文字列・数値変換はせず、`std::getenv(...) != nullptr` だけで判定します。したがって `0`、`false`、空文字も有効です。`=1` はコメント上の例であり、実装上の必須値ではありません。判定は `launch_wmma()` が最初に呼ばれたときに `static const bool` へ保存されます。

## 有効になる条件

診断は HIP build の `launch_wmma()` に入った場合に限られ、さらにその呼び出しの `n_q >= 2048` で、プロセス内の対象呼び出し回数がまだ4回未満のときに実行されます。回数は `n_q >= 2048` の呼び出しだけで増えます。従って、環境変数が有効でも CUDA build、小さい query batch、または5回目以降の対象呼び出しでは診断しません。

`launch_wmma()` に到達するには、QSA prompt attention が次の条件を満たす必要があります。

- HIP build であり、現在の GPU が対応する gfx11 または gfx12 である（それ以外は WMMA を使わない）。
- Q/K/V pool が必要な int8 pool と scale を持ち、Q4 pool ではなく、geometry が `head_dim == 256` かつ `n_head == 12 * n_head_kv`、`cap > 0`、selection buffer が揃っている。
- `STRATA_HIP_WMMA` の判定で WMMA が許可される。先頭文字が `1` の値で gfx11/gfx12 を強制、完全一致の `auto` は gfx12 のみで `STRATA_HIP_WMMA_MIN_Q`（既定64）と `STRATA_HIP_WMMA_MIN_CAP`（既定0）を満たす場合、未設定または空文字は gfx12 のみで有効です。未設定時の gfx12 既定は非 Windows build で ON、Windows で OFF。`STRATA_HIP_WMMA=0` や `true` など、それ以外の値は OFF です。失敗済み状態や WMMA 非対応 architecture でも使われません。

この診断は通常の prefill が `qsa_prompt_attn_batch()` を呼ぶ経路（`src/prefill/prefill.cpp`）のほか、HIP の `hip_prompt_attn_wmma` parity 実行ファイルからも到達し得ます。後者は既定で query 数 2048 を指定します。

## 実行時の詳細

有効かつ条件を満たす呼び出しでは、まず stream を同期し、`ids` と `steps` を host vector にコピーします。その後 query 群の後半を走査し、連続する `R = 4, 8, 16, 32` query ごとに各 query の選択数と選択 cell の union を集計します。各 R について group があれば、選択数の平均、union 数の平均、`mean union / mean selection`、および `R * mean selection / mean union` を stderr の次の形式で出力します。

```text
strata qsa stat: call ... n_q ... cap ... rows/group ...: mean selection ..., mean union ... (x...; K/V reads per row ...x lower)
```

この処理は attention kernel の起動前に行われるため、実行同期・device-to-host 転送・host 集計を追加します。ログ中の K/V read 数は計算した選択重複からの目安であり、このコードが row-union attention に切り替えたり K/V 読み出しを削減したりするわけではありません。診断部分に固有の警告・終了処理はありません。直後の WMMA kernel launch 自体が失敗した場合は `qsa_prompt_attn_batch (wmma): ...; the FP32 prompt attention runs from here on` を stderr に出し、WMMA を以後無効化して呼び出し側の FP32 経路へ戻します。

読み取りと `n_q`・回数条件: `src/kernels/cuda/qsa_prompt_attn.cu:2246-2255`。集計とログ: 同 `2257-2274`。HIP の build guard、対応 architecture、WMMA 選択条件: 同 `1885-1905,2190-2244,2404-2412`。gfx12 の platform 既定: `include/strata/core/gfx12_platform_defaults.hpp:10-16`。

## 根拠

`STRATA_QSA_STAT` の完全一致検索では参照は `src/kernels/cuda/qsa_prompt_attn.cu:2248-2249` のみで、環境値の読み取りも同所だけです。読み取りは `launch_wmma()` 内にあり、呼び出し元 `qsa_prompt_attn_batch()` は HIP 分岐で条件を満たす場合にだけそこへ進みます（同 `2404-2412`）。通常の prefill 呼び出しは `src/prefill/prefill.cpp:4073-4097,7061-7071`、HIP parity 実行ファイルと既定 query 数は `CMakeLists.txt:1108-1111` および `src/kernels/qsa_prompt_attn_parity.cpp:10-11,214-218` です。

`docs/DETAILS.md` にこの変数の説明や測定値は見つかりませんでした。本調査ではソースの診断計算と出力のみを記載し、外部ライブラリや driver の挙動は扱っていません。
