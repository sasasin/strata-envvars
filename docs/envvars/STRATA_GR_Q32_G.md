# `STRATA_GR_Q32_G`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP の Q8 fused hyper-connection read で、Q32 up-kernel が warp ごとにまとめてロードする行数 `G` を選ぶ。値 `2` / `4` / `8` はそれぞれ `gr_up_q8_q32_kernel<T, G>` を起動し、それ以外は `G=1` を使う。`G` は up read のロード順序とグループ化を変えるが、カーネル内コメントでは各行の演算は変わらず出力は bitwise 同一とされている（`engine/src/kernels/cuda/fused_gr.cu:2400-2417,4024-4031`）。

この変数を読む実装は `launch_q8_t<T>` の 1 箇所。CUDA と HIP gfx906 のビルドでは `STRATA_GR_FAST_BUILD` が 1 になり、この読み取りと分岐はコンパイル対象にならない。HIP の gfx906 以外では 0 になり、対象分岐がコンパイルされる（`engine/src/kernels/cuda/fused_gr.cu:48-53,4024-4032`）。

`docs/DETAILS.md` の CUDA opt-in kernel 一覧にはこの変数の記載がなく、対象分岐の測定値も示されていないため、性能効果は記載しない（`docs/DETAILS.md:1288-1305`）。

## 値と判定

値は `std::getenv` で取得し、設定されていれば `std::atoi` の戻り値を使う。文字列全体の検証はなく、数値として先頭から読めた部分で判定される。受理値は `2`、`4`、`8` のみ。それ以外と未設定は `1` にフォールバックする（`engine/src/kernels/cuda/fused_gr.cu:4026-4030`）。

| 条件 | unset | 有効になる値（例） | 無効値・fallback の例 |
|---|---|---|---|
| HIP、gfx906 以外、後述の Q32 分岐を実行 | `G=1` | `2`, `4`, `8` | 空文字、`0`, `1`, `3`, `9`, `-2`, `true` は `G=1` |
| CUDA または HIP gfx906 | カーネル分岐自体がビルドされない | なし | 設定値をこのコードは読まない |

`atoi` のため、先頭空白や符号は許容され、後続文字は検査されない（例: `"  +2tail"` は `2`、`"4.0"` は `4` と判定）。大文字小文字を区別する文字列比較はしない。数値変換が 2 / 4 / 8 以外になる値は `1` を選ぶ。整数変換の範囲外の文字列に対する `atoi` の結果は文書化可能な規則として扱わない。

## 有効になる条件

- `STRATA_GR_FAST_BUILD=0` 相当の HIP 非 gfx906 ビルドであること。CUDA ビルドでは有効にならない（`engine/src/kernels/cuda/fused_gr.cu:48-53,4024-4032`）。
- `fused_gr_read_multi` が fused GR 経路として呼ばれ、`q8_down` と `q8_up` の両方が非 null で `launch_q8` に進むこと（`engine/src/kernels/cuda/fused_gr.cu:4285-4293`）。
- その Q8 読み取りで `q8_mixed` が非 null かつ `qfuse_hc_local()` が true であること。この helper は `STRATA_QFUSE_HC_LOCAL` が未設定なら true、設定時は `atoi(value) != 0` を返す。偽なら本変数の分岐を通らず、後続の別 up-kernel 経路へ進む（`engine/src/kernels/cuda/fused_gr.cu:1553-1557,4024-4035`）。
- 通常の `generate` では fused GR 自体も、`--no-fused-gr` がなく、native MMVF が有効で、GPU stages / layer dump / half dump / stage timing を使わない場合に設定される（`engine/src/program/generate.cpp:6104-6113`）。
- `q8_mixed` の有無は呼び出し側の量子化バッファ状態にも依存する。たとえば verifier は `qcnt_` がある場合に `q8_mixed` を設定し、persist 読み取りは `q8_mixed` を設定しない（`engine/src/core/verify.cpp:1810-1818`）。`qcnt_` は `STRATA_QFUSE` または `STRATA_QFUSE_HC` が有効な場合に確保される（`engine/src/core/verify.cpp:1431-1437`）。
- HIP MTP 経路では `STRATA_QFUSE_HC` による下書き層向け Q8_1 出力の選択も `q8_mixed` 設定に関係する。既定時は gfx12 のみ有効で、他の GPU では別途有効化が必要（`engine/src/core/mtp.cpp:1137-1158,1229-1241`）。

## 実行時の詳細

`launch_q8_t<T>` は Q8 の down kernel を起動した後、`q8_mixed != nullptr && qfuse_hc_local()` の場合に `G` を読み、`gr_up_q8_q32_kernel<T,G>` を起動して関数から戻る。Q32 カーネルは各 warp が `G` 行の重み等をまとめてロードしてから処理し、32 列のブロックがその範囲の Q8_1 画像も書く。`G=1` は通常の 1 行ロード、`G=2/4/8` は複数行のロードグループであり、ソースコメントは各行の算術結果が同一と説明する（`engine/src/kernels/cuda/fused_gr.cu:2400-2417,2474-2525,4024-4032`）。

値は `launch_q8_t<T>` の関数テンプレート特殊化ごとの関数内 `static const int` に初回評価時保存される。したがって各 `T` の分岐が初めて実行された後は、プロセス内で環境を変更してもその特殊化には反映されない。初期化前の特殊化には、その時点の環境値が使われる（`engine/src/kernels/cuda/fused_gr.cu:4026`）。

Strata は AMD の起動時アーキテクチャ既定値として `gfx1200/1201` に `2` を設定するほか、離散 RDNA3 の `gfx1100/1101/1102` にも `2` を設定する。`STRATA_GFX12_DEFAULTS=0`、`STRATA_GFX11_DEFAULTS=0`、または `STRATA_DEFAULTS=026` により該当する既定値表が外れる。既に環境変数が設定されていると既定値適用は上書きしない。gfx12 の表は `defaults026` 時に `STRATA_GR_Q32_G` を追加する前に戻り、gfx11 の表も defaults026 時は無効となる（`engine/src/core/arch_defaults.cpp:30-62,302-323`; `engine/include/strata/core/gfx11_extra.hpp:27-46,55-72`）。通常の `generate` では HIP の初期化中に GPU 0 のアーキテクチャを取得して既定値を適用する（`engine/src/program/generate.cpp:4287-4320`）。

## ログと測定値

この変数だけに対する警告やログはない。gfx12 の既定値が新たに設定された場合は、「`strata: gfx12 (RDNA4): %zu exact speed switches on by default ...`」の一覧、離散 gfx11 の場合は「`strata: gfx11 (RDNA3): %zu exact speed switches on by default ...`」の一覧に `GR_Q32_G` が含まれる（`engine/src/core/arch_defaults.cpp:312-332,397-404`）。明示値が既にある場合は既定値一覧に追加されない。Q8 kernel 起動後の CUDA/HIP エラーは `fused_gr_read_multi q8: %s` を stderr に出して `exit(1)` するが、エラー理由をこの環境変数に結び付ける処理はない（`engine/src/kernels/cuda/fused_gr.cu:4286-4293`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:48-53,2400-2417,4024-4032` — backend/build 条件、Q32 カーネルと値判定。
- `engine/src/kernels/cuda/fused_gr.cu:1553-1557,4285-4293` — `STRATA_QFUSE_HC_LOCAL` ゲート、Q8 経路と失敗時の扱い。
- `engine/src/core/verify.cpp:1431-1437,1803-1818` — verifier の Q8 状態と `q8_mixed` 設定。
- `engine/src/core/mtp.cpp:1137-1158,1229-1241` — MTP の QFUSE_HC 条件。
- `engine/src/core/arch_defaults.cpp:30-62,218-223,302-332,397-404` — gfx12 の既定値・適用・ログ。
- `engine/include/strata/core/gfx11_extra.hpp:27-46,55-72` — 離散 RDNA3 の既定値条件。
- `engine/src/program/generate.cpp:4287-4320,6104-6113` — 起動時のアーキテクチャ既定値と fused GR 有効条件。
