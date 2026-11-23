# `STRATA_HIP_FAST_DEC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP AMD ビルドで RDNA 向け decode kernel を選べるようにする。対象コードは Q6_K / K-quant / Q8_0 の MMVQ (`rdna_mmvq.cu`) と hyper-connection read (`rdna_gr.cu`) である。値が有効でも、各呼び出し側の型・形状条件を満たさない処理はこの経路を使わない。CUDA ビルド、HIP の gfx906、および AMD HIP 以外のコンパイルでは RDNA 実装が無効である。`engine/src/kernels/cuda/rdna_mmvq.cu:20-22,377-385,484-490`、`engine/src/kernels/cuda/rdna_gr.cu:25-26,548-565,593-598`

## 値と判定

両 kernel は関数内 `static const int` 初期化で環境を読む。優先順位はそれぞれ `STRATA_RDNA_Q6K` → `STRATA_HIP_FAST_DEC`（MMVQ）、`STRATA_GR_RDNA` → `STRATA_HIP_FAST_DEC`（GR）。先行する専用変数が設定済みなら、値が空でも `STRATA_HIP_FAST_DEC` は調べない。対象変数は未設定ならその箇所では無効、設定済みなら `value[0] == '1'` のときだけ有効候補となる。文字列全体や数値としての妥当性は検査しない。

| 条件 | `STRATA_HIP_FAST_DEC` | 結果 |
|---|---|---|
| 専用変数が未設定 | unset | 無効（自動既定値が適用された場合を除く） |
| 専用変数が未設定 | `1`, `1anything` | 有効候補。さらにデバイス世代を確認 |
| 専用変数が未設定 | 空文字、`0`, `0anything`, `true`, ` 1`, `-1` | 無効 |
| 専用変数が設定済み | 任意の値（空文字を含む） | 専用変数の判定が使われ、対象変数は無視 |
| 起動時の gfx11 WMMA 既定値対象 | unset | `1` を設定（下記条件・抑止変数に従う） |
| 起動時の gfx11 WMMA 既定値対象 | 任意の設定値 | ユーザー設定を保持。自動上書きしない |

MMVQ 側では `STRATA_RDNA_Q6K` が設定されていれば同変数の先頭文字だけで有効・無効を決め、`1` ならアーキテクチャ検査を省略する。未設定の場合に限り本変数を読み、`1` の場合は gfx11 WMMA 対応または gfx12 を確認する。GR 側も同様に `STRATA_GR_RDNA` を優先し、専用変数が `1` なら世代検査なしで有効、対象変数経由なら gfx11 WMMA 対応または gfx12 のデバイスに限り有効となる。`engine/src/kernels/cuda/rdna_mmvq.cu:377-385`、`engine/src/kernels/cuda/rdna_gr.cu:548-565`

Strata の `apply_arch_defaults` は環境変数の有無（値の内容ではない）を調べ、既存の設定を上書きしない。したがって空文字や `0` もユーザー設定として扱われ、自動的な `1` の設定を止める。通常の CLI 引数でこの変数を上書きする処理は確認できない。`engine/src/core/arch_defaults.cpp:307-310,334-345`

## 有効になる条件

- RDNA の実装は `__HIP_PLATFORM_AMD__` かつ `STRATA_HIP_GFX906` 未定義のビルドでのみ実体を持つ。それ以外の分岐は `false` を返す。アプリ起動時の自動既定値処理も `STRATA_USE_HIP` のビルドに限られる。`engine/src/kernels/cuda/rdna_mmvq.cu:20-22,484-490`、`engine/src/kernels/cuda/rdna_gr.cu:25-26,593-598`、`engine/src/program/generate.cpp:4282-4286`
- `STRATA_HIP_FAST_DEC=1` による有効化は、現在の GPU が gfx11 WMMA 対応または gfx12 であることが必要。デバイス取得・属性取得に失敗した場合も無効となる。デバイス判定結果はデバイス番号ごとに cache される。`engine/src/kernels/cuda/rdna_mmvq.cu:352-372,377-385`、`engine/src/kernels/cuda/rdna_gr.cu:556-564`
- 起動時に自動で `1` が補われるのは gfx11 discrete の WMMA 既定値（gfx1100 / gfx1101 / gfx1102）か、Windows 上の統合 gfx1151（Strix Halo）の prompt set に該当し、かつこの変数が未設定の場合。gfx11 discrete では `STRATA_DEFAULTS=026`、`STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0` が既定値セットを抑止する。統合 gfx1151 Windows の prompt set は `STRATA_IGPU_DEFAULTS=0` または `STRATA_IGPU_PROMPT_SET=0` で抑止できる。統合 GPU の自動適用には、見えている GPU がすべて統合型で同一アーキテクチャという起動側条件もある。`engine/include/strata/core/gfx11_extra.hpp:27-36,87-109`、`engine/src/core/arch_defaults.cpp:193-213,334-345`、`engine/src/core/arch_defaults.cpp:172-180`、`engine/src/program/generate.cpp:4287-4296,4315`
- gfx11 discrete 既定値対象は gfx1100 / gfx1101 / gfx1102。Windows gfx1151 は統合 GPU の prompt set を通じて対象になる。Linux gfx1151、gfx1103 / gfx1150、および gfx12 に対するこの変数の自動設定は確認できない。ただし HIP 実行中に明示的に `1` を設定すれば、上記 kernel の世代判定は gfx12 も受け付ける。`engine/include/strata/core/gfx11_extra.hpp:87-109`、`engine/src/core/arch_defaults.cpp:193-213`、`engine/src/kernels/cuda/rdna_mmvq.cu:377-385`、`engine/src/kernels/cuda/rdna_gr.cu:548-565`
- MMVQ では型・形状によって RDNA 関数が `false` を返すと呼び出し元が通常経路へ進む。対象は Q6_K、Q4_K / Q5_K / IQ4_XS / IQ3_S、および一部の Q8_0 経路で、入力幅・列数などの条件もある。Q4_K / Q5_K は列数 4 未満では `STRATA_RDNA_KQ_ALL` が未設定なら不使用。Q8_0 WMMA decode は別途 `STRATA_RDNA_Q80_WMMA` の先頭文字が `'0'` なら無効になる。`engine/src/kernels/cuda/rdna_mmvq.cu:391-431,438-481`、`engine/src/kernels/cuda/native_mmvq.cu:3319,3526,3567,3609,3702,3814`
- GR 経路は `fused_gr_read_multi` で、入力に `q8_down` と `q8_up` の両方がある場合は本変数判定より前に別の `launch_q8` 経路を使う。`engine/src/kernels/cuda/fused_gr.cu:4284-4301`

## 実行時の詳細

アプリ起動時、HIP ビルドは GPU 情報を取得した後、`apply_arch_defaults` を呼び出す。該当する gfx11 既定値セットでは本変数が未設定のときだけ `1` をプロセス環境に設定し、ユーザーが設定済みなら保持する。これは CLI 優先順位ではなく環境変数の有無による既定値補完である。`engine/src/program/generate.cpp:4282-4296,4315`、`engine/src/core/arch_defaults.cpp:302-310,334-345`

MMVQ と GR は、それぞれの有効判定関数が初めて呼ばれたときに専用変数と本変数を一度評価し、結果を `static` に保存する。プロセス実行中に環境を変更しても、この判定は更新されない。デバイス世代の照会結果も GPU 番号ごとに cache される。`engine/src/kernels/cuda/rdna_mmvq.cu:377-385`、`engine/src/kernels/cuda/rdna_gr.cu:548-564`

選択された MMVQ 関数は条件を満たせなければ `false` を返し、呼び出し元は次の通常実装へ続く。GR 側は選択後に RDNA read を実行し、CUDA/HIP の最終エラー状態を検査する。エラー時は stderr にエラーを表示して `exit(1)` する。`engine/src/kernels/cuda/rdna_mmvq.cu:391-431,438-481`、`engine/src/kernels/cuda/native_mmvq.cu:3319,3526,3567,3609,3702,3814`、`engine/src/kernels/cuda/fused_gr.cu:4293-4300`

## ログと測定値

gfx11 既定値が一つ以上適用されると stderr に `strata: gfx11 (RDNA3): %zu matrix-core prompt & MoE switches on by default (STRATA_GFX11_WMMA_DEFAULTS=0 or STRATA_GFX11_DEFAULTS=0 turns them off; NAME=0 turns one off): ` と出力され、一覧に `HIP_FAST_DEC` が含まれる。対象変数を明示設定済みの場合は自動設定されず、この一覧には含まれない。kernel の有効判定自体が理由ログを出すコードは確認できない。`engine/src/core/arch_defaults.cpp:334-345`

GR の RDNA 実行後にエラーがあれば stderr に `fused_gr_read_multi rdna: <CUDA/HIP error string>` を出してプロセスを終了する。Q8 経路のエラーには別の `fused_gr_read_multi q8: ...` がある。`engine/src/kernels/cuda/fused_gr.cu:4284-4299`

## 根拠

- 読み取り、値判定、cache、アーキテクチャ判定: `engine/src/kernels/cuda/rdna_mmvq.cu:352-385`、`engine/src/kernels/cuda/rdna_gr.cu:548-565`
- 自動既定値の対象、抑止条件、既存値の保持: `engine/include/strata/core/gfx11_extra.hpp:27-36,87-109`、`engine/src/core/arch_defaults.cpp:193-213,302-345`
- 起動時の適用条件と呼び出し: `engine/src/program/generate.cpp:4282-4296,4315`
- MMVQ の呼び出し条件と通常経路への復帰: `engine/src/kernels/cuda/rdna_mmvq.cu:391-481`、`engine/src/kernels/cuda/native_mmvq.cu:3319,3526,3567,3609,3702,3814`
- GR の分岐、エラー表示、終了: `engine/src/kernels/cuda/fused_gr.cu:4284-4301`
