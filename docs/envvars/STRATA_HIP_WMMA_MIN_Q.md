# `STRATA_HIP_WMMA_MIN_Q`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の prompt QSA attention で `STRATA_HIP_WMMA=auto` を指定したとき、RDNA4（gfx12）の matrix-core WMMA kernel を選ぶ最小 query 数を指定します。呼び出しの query 数がこの値以上で、さらに context capacity が `STRATA_HIP_WMMA_MIN_CAP` 以上なら WMMA kernel を使います。条件に届かなければ、この関数は WMMA を使わず、呼び出し元の既存 FP32 prompt attention 経路に戻します。

## 値と判定

| 環境変数の状態 | 閾値 |
|---|---:|
| 未設定 | `64` |
| 設定あり | `std::atoll()` で変換した符号付き整数 |

変換結果は clamp も範囲検査もされません。`atoll()` は先頭の空白と符号を許し、整数として読める先頭部分を変換します。空文字や数値で始まらない文字列は `0` になり、数値の後ろに文字が続いてもその部分は判定に使われません。したがって `64junk` は `64`、`-1` は `-1` として扱われます。負値なら通常の正の `n_q` はこの閾値を満たします。

## 有効になる条件

- `STRATA_HIP_WMMA=auto` が選ばれていること。`STRATA_HIP_WMMA=1` は閾値判定を通らず、対応する matrix-core 経路を強制します。`=0` は無効にします。
- 現在の GPU が gfx12 であること。`auto` は gfx11 では WMMA を選びません。
- prompt attention 呼び出しが正の `cap`、query/page 情報、int8 KV の K/V と scale、対応する shape を持つこと。満たさない場合は WMMA 判定に進まず、呼び出し元が別経路を使います。
- `n_q >= STRATA_HIP_WMMA_MIN_Q` に加え、`cap >= STRATA_HIP_WMMA_MIN_CAP` であること。`STRATA_HIP_WMMA_MIN_CAP` が未設定ならその下限は `0` です。

WMMA が既定で有効な gfx12 経路（Linux）では、`STRATA_HIP_WMMA_MIN_Q` は選択に使われません。逆に Windows の既定 OFF をこの変数だけで有効化することもできません。既定の on/off は `STRATA_HIP_WMMA` の実装と `kGfx12PromptDefaultsOn` によります。

## 実行時の詳細

`hip_wmma_auto_pick()` 内の `static const` 初期化で一度読み取られます。読み取りは `auto` の gfx12 判定が実際にこの関数へ到達したときに行われ、その後プロセス内で環境変数を変更しても閾値は更新されません。設定は当該プロセス内の prompt attention 選択に適用されます。

WMMA の起動が失敗すると `launch_wmma()` が stderr に `qsa_prompt_attn_batch (wmma): ...; the FP32 prompt attention runs from here on` と出し、残りのプロセス実行では WMMA を無効にして FP32 経路に戻します。この fallback は query 閾値による分岐とは別です。

## 文書との照合

`docs/AMD_HIP.md` は `STRATA_HIP_WMMA=auto` を gfx12 の per-call 選択として説明し、既定の最小 query 数を 64 と記しています。今回確認した実装の既定値と一致します。同資料にある性能値は R9700 など記載の条件に限った測定であり、この閾値を変更した場合の性能や品質を保証するものではありません。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:2224-2229`: gfx12 のみを対象とし、`STRATA_HIP_WMMA_MIN_Q`（既定64）と `STRATA_HIP_WMMA_MIN_CAP` を比較。
- `src/kernels/cuda/qsa_prompt_attn.cu:2230-2239`: `auto` 時のみ query/cap 判定を呼び、既定経路と強制モードを分岐。
- `src/kernels/cuda/qsa_prompt_attn.cu:2372-2380`: HIP prompt batch で int8 KV 等の shape・入力条件を確認し、条件成立時に WMMA kernel を起動。
- `src/kernels/cuda/qsa_prompt_attn.cu:2258-2264`: WMMA launch error のログ、以後の失敗フラグ設定。
- `docs/AMD_HIP.md:497-521`: WMMA の既定条件、`auto` の説明と資料記載の測定条件。
