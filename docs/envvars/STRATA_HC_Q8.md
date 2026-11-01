# `STRATA_HC_Q8`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

Hyper-connection (HC) down/up 等の重みを、検証・decode の read で Q8_0 として使うための切替です。ただし backend と実行経路で意味が異なります。

- CUDA/HIP の `NativeDense` 経路では、native dense GGUF 内の対応 HC 行にある Q8_0 データを読み込みます。HIP の対応 AMD GPU では、native dense 経路の BF16 行から Q8_0 コピーを作る機能も既定で有効になります。
- Metal は `Window` の初期化時に BF16 HC 行を Q8_0 化し、decode window の HC read でそのコピーを選びます。Metal では既定で有効です。
- SYCL は native dense GGUF の Q8_0 行をロードして verify 引数に設定しますが、SYCL の fused HC read に Q8_0 読み取りカーネルは実装されていません。このため、この経路で Q8_0 が実際の HC 重み read に使われるとは確認できません。

これは一般の BF16 pack に対する切替ではありません。CUDA/HIP の通常 pack 経路に別途ある `STRATA_HC_REQ8` とは異なります（`src/program/generate.cpp:4516-4524`）。

## 値と判定

各判定は初回評価時の値を `static` に保存するか、Metal では `Window` の初期化時にメンバーへ保存します。数値全体の parse を共通に行う仕様ではありません。

| backend / 条件 | 未設定・空文字・`auto` | 設定値の判定 |
|---|---|---|
| CUDA（HIP 以外）の `NativeDense` | OFF | 先頭文字が `1` ならON（例: `1`, `10`, `1anything`）。それ以外はOFF。 |
| HIP `NativeDense`、gfx1151 | 自動でON | 先頭文字が `1` ならON。空でない値が厳密に `auto` 以外なら明示指定として扱い、先頭が `1` でなければOFF（`0`, `true`, `autofoo` 等）。 |
| HIP `NativeDense`、gfx12（gfx1151以外） | gfx12 既定が許可されていれば自動判定 | 先頭文字が `1` ならON。空でない値が厳密に `auto` 以外なら、先頭が `1` でなければOFF。自動判定では `STRATA_GFX12_DEFAULTS` の先頭文字が `0` ならOFF、それ以外は gfx12 のときON。 |
| SYCL `NativeDense` | OFF | 先頭文字が `1` ならON。その他はOFF。 |
| Metal | ON | 値全体が文字列 `0` と一致するときだけOFF。それ以外はON。 |

CUDA/HIP の判定は `src/core/native_dense.cpp:46-83`、SYCL は `sycl/src/core/native_dense.cpp:32-36`、Metal は `metal/src/engine/window.cpp:671-676` にあります。HIP では gfx1151 の自動判定が `STRATA_GFX12_DEFAULTS` の確認より先です。したがってこの別変数で gfx1151 の既定を無効にはできません。空文字は HIP の `auto` と同じ自動判定に入りますが、SYCL ではOFF、Metal ではONです。

## 有効になる条件

### CUDA / HIP

`STRATA_HC_Q8` を読むのは `NativeDense` です。生成時に `--native-dense` 相当の native dense GGUF が指定され、native dense loader が実行される経路に限られます。`NativeDense::hc_q8_requested()` は、native dense GGUF があり、単一 GPU で、canonical 重みを残さない場合に pack の層 down/up 行を skip set に加える条件にも使われます（`src/program/generate.cpp:4447-4468`）。一方、別の `STRATA_HC_REQ8` は通常 pack に適用される独立の切替です。

Q8_0 の native dense tensor がある場合、loader は `blk.*.hc_{attn,ffn}_{down,up,inject}.weight` と `output_hc_{down,up}.weight` の対応行を登録します。BF16 pack 由来の追加量子化は、`blk.*` の down/up 行が対象で、層範囲、canonical 行の有無、形状が条件になります。Q8_0 の inject 行は読み込みます。BF16 inject 行を Q8_0 化するには別変数 `STRATA_HC_Q8_INJECT` の先頭文字も `1` である必要があります。BF16 pack の output mixer および inject 行はこの down/up 追加量子化ループの対象ではありません（`src/core/native_dense.cpp:85-92,398-460`）。

HIP の自動ONは GPU の device properties から gfx1151 または gfx12 と判定できた場合です。device query が失敗するか、他の GPU なら自動ではONになりません（`src/core/native_dense.cpp:54-80`）。CUDA（HIP以外）にアーキテクチャ既定はありません。

### SYCL

SYCL の `NativeDense` 経路だけが対象です。loader は Q8_0 の対応 HC 行をアップロードし、verify 側で down/up/inject の Q8 ポインターを `FusedGrArgs` に設定します（`sycl/src/core/native_dense.cpp:321-357`, `sycl/src/core/verify.cpp:1005-1023,1635-1649`）。ただし SYCL の `fused_gr_read_multi` は Q8_0 read kernel を実装しておらず、同関数にその旨のコメントがあります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2046-2053`）。したがって env がONでも、ソース上は Q8_0 の HC read が実行されるとは確認できません。

### Metal

Metal engine の `Window` 構築時に判定し、モデル内の HC tensor を走査します。BF16 tensor のうち `hc_` を含み `_norm` を含まないものを Q8_0 に変換します。`STRATA_HC_Q8=0` なら BF16 行を使い、ONならストリーミング時に Q8 コピー対象の BF16 原本を読み飛ばします。read 時も Q8 コピーがある名前では Q8_0 を選びます（`metal/src/engine/window.cpp:671-727,2630-2639`）。Q6_K / IQ4_NL の HC tensor はこの変数の値にかかわらず変換対象です（同 `:683-686`）。

## 実行時の詳細

CUDA/HIP の `hc_q8_env()` は最初の呼び出しで環境値と、必要なら GPU 世代を評価し、結果をプロセス内で cache します。初回評価後の環境変更は再評価されません。Q8_0 tensor は native dense GGUF からアップロードし、BF16 pack の対象 down/up 行は Q8_0 に量子化して `WeightRef::hc_q8` に格納します。BF16 原本が skip される経路では prompt / 単一 token read 用の BF16 scratch も load 時に確保し、必要なときに Q8_0 から戻します（`src/core/native_dense.cpp:398-479,534-553`）。verify はこの Q8 ポインターを fused HC read に渡し、final mixer でも down/up の Q8 コピーが両方存在し、head が loaded の場合に Q8 read を選びます（`src/core/verify.cpp:1457-1479,2386-2407`）。

CUDA/HIP では不正な行形状、GPU allocation/upload、quantize、scratch/event 作成に失敗すると loader はエラー文字列を返します。呼び出し元は `strata generate: native dense projections: ...` を stderr に出して終了コード 1 で戻ります（`src/core/native_dense.cpp:408-418,432-478`; `src/program/generate.cpp:4592-4597`）。load 成功時、Q8_0 HC 投影の総量を `strata: STRATA_HC_Q8=1: ... GiB of Q8_0 hyper-connection projections for the verify read` と stderr に出します（`src/core/native_dense.cpp:508-512`）。HIP 自動ON時は gfx1151 または gfx12 の説明ログも stderr に出ます（同 `:63-77`）。

Metal の判定は `Window` ごとに一度行われます。変換に失敗したストリーム読み込みは `strata metal: read failed` を出して `exit(6)` します。変換処理後には `strata metal: HC read in Q8_0 ...` の統計ログを stderr に出します（`metal/src/engine/window.cpp:674-721`）。

## 根拠

- 値判定と HIP 世代既定: `src/core/native_dense.cpp:46-83`; SYCL 判定: `sycl/src/core/native_dense.cpp:32-36`; Metal 判定: `metal/src/engine/window.cpp:671-676`。
- 対象 HC tensor 名と CUDA/HIP の native dense 読込・BF16 行量子化: `src/core/native_dense.cpp:85-92,398-479`; native dense の生成条件: `src/program/generate.cpp:4447-4468,4592-4597`。
- Q8 ポインターを使う CUDA/HIP verify read: `src/core/verify.cpp:1457-1479,2386-2407`; SYCL の転送と kernel 制限: `sycl/src/core/native_dense.cpp:321-357`, `sycl/src/core/verify.cpp:1005-1023,1635-1649`, `sycl/src/kernels/cuda/fused_gr.dp.cpp:2046-2053`。
- 既存資料との照合: HIP gfx12/gfx1151 の既定と BF16 fallback は `docs/AMD_HIP.md:298,679-684`、Metal の既定と `=0` は `docs/MAC.md:130-134,243-250`、NVIDIA 上の Unsloth pack 設定は `setup.py:3943-3957` に記載されています。これらの資料中の性能値は測定条件付きの資料記載であり、本調査で再測定していません。
