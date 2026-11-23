# `STRATA_PF_P1A_PLAIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_PF_P1A_PLAIN` は、HIP の P1A MoE prompt カーネルで使う FL=3（IL + double buffering）実装を抑止するスイッチです。値が `1` で始まると `p1a_fast_flags()` が `false` を返し、`gate_up` と `down` はテンプレート既定のカーネルを選びます。P1A 経路そのものを有効化・無効化する変数ではありません。P1A 経路の選択は主に `STRATA_PF_P1A` が担います（`engine/src/prefill/moe_p1a.cu:514-520,534-556`; `engine/src/prefill/moe_fused_iq.cu:3612-3621,3703-3714`）。

## 値と判定

| 条件 | unset | 有効になる値（FL=3 を抑止） | 無効になる値（この変数による抑止なし） |
|---|---|---|---|
| P1A カーネル内の判定 | 後続の `STRATA_PF_P1A_FL3`、それも未指定なら GPU 判定へ | 先頭文字が `1` なら `false` を返し、FL=3 を選ばない | 空文字、`0`、`true`、`01` など先頭文字が `1` でない値はこの分岐に一致せず、後続判定へ進む |

`std::getenv` の null 判定と `p[0] == '1'` だけを使い、文字列全体の比較・数値変換・空白除去はしません。したがって `1`, `10`, `1anything` は抑止し、`0`, `true`, 空文字は抑止しません。大文字小文字を含む先頭文字が `1` でなければ一致しません（`engine/src/prefill/moe_p1a.cu:514-520`）。

この変数が `1` で始まらない場合、`STRATA_PF_P1A_FL3` が空でなく設定されていれば、その先頭文字が `1` のときだけ FL=3 を選びます。つまり `STRATA_PF_P1A_PLAIN=1` は `STRATA_PF_P1A_FL3` より優先されますが、`STRATA_PF_P1A_PLAIN=0` や空文字は `STRATA_PF_P1A_FL3` の指定を打ち消しません。両方が未設定（または FL3 が空）のときは後述の GPU 判定を使います（同 `:515-531`）。

## 有効になる条件

- 値の効果が現れるのは `engine/src/prefill/moe_p1a.cu` の P1A カーネルが呼ばれた場合だけです。このソースは HIP backend の `strata_pf_own` に組み込まれます（`engine/cmake/backends/hip.cmake:30-46`）。
- P1A 経路自体は HIP build で `STRATA_PF_P1A` が文字列全体として `1` であり、デバイスが `g11_wmma` の場合に要求されます。CUDA build 側の `p1a_wanted()` は常に `false` です（`engine/src/prefill/moe_fused_iq.cu:3612-3621`）。
- 実際の P1A kernel 呼び出しにはさらに、prompt の fused native 経路から FP16 入力が渡されていること、FP16 down 出力が要求されること、down rotation が無効であること、対象 pair が対応する型であること、tile 数が `65535` 以下であること、FP16 H 用のバッファ容量が足りることが必要です。条件を満たさない呼び出しは後続の通常経路に進みます（同 `:3656-3663,3686-3714`）。
- 基本の型 pair は Q4_K gate/up + Q5_1 down です。別変数 `STRATA_PF_P1A_L2` が文字列全体で `1` の場合は Q5_K gate/up と Q8_0 down も含まれます（`engine/src/prefill/moe_p1a.cu:509-512`; `engine/src/prefill/moe_fused_iq.cu:3623-3629`）。
- 値が未設定か先頭が `1` 以外で、`STRATA_PF_P1A_FL3` も未指定・空の場合、FL=3 は GPU ごとに一度調べた device property が discrete RDNA3 と判定された場合だけ選ばれます。現在の device 取得失敗、device index が 0–63 の範囲外、property 取得失敗、または discrete RDNA3 以外では FL=3 を選びません（`engine/src/prefill/moe_p1a.cu:521-531`）。

この変数に CLI 引数や設定ファイルから優先する経路は、ソース全体の参照調査では見つかりません。`STRATA_PF_P1A` の有効化やアーキテクチャ既定値とは別の、FL=3 の選択制御です（`engine/src/core/arch_defaults.cpp:202-210`; `engine/src/prefill/moe_p1a.cu:514-531`）。

## 実行時の詳細

判定は `p1a_fast_flags()` 内の関数ローカル `static const int env` の初期化時に行われ、そのプロセス内でキャッシュされます。環境変数は gate/up または down が最初にこの関数を呼ぶ時に読み取られ、実行中に値を変えても再評価されません。`STRATA_PF_P1A_PLAIN` が先頭 `1` ならその時点で結果が確定し、FL3 や GPU 判定は読みません。そうでなければ FL3 を確認し、それも適用されない場合に GPU 判定へ進みます。GPU 判定結果は `arch_fl3[dev]` に device ごとにキャッシュされます（`engine/src/prefill/moe_p1a.cu:514-531`）。

`fast == true` のとき gate/up と down は FL=3 の明示的なテンプレート構成を起動し、`false` のときは既定テンプレート構成を起動します。従って値は kernel variant を選びますが、P1A の利用可否、型 pair、入力・出力データ自体を直接変更しません（同 `:534-556`）。P1A 実行後の `cudaGetLastError()` は失敗時に stderr へ `prefill fused experts (native): experts_native (P1A): <error>` を出し、終了コード 1 で終了します（`engine/src/prefill/moe_fused_iq.cu:68-72,3709-3714`）。

## ログと測定値

この変数を読んだことや FL=3 を抑止したことだけを示すログはありません。P1A kernel が実際に使われた layer がある場合は、最初の fused prompt chunk の最終 layer で stderr に `strata: prompt experts P1A (STRATA_PF_P1A=1): gate/up + down on the P1A kernels in ...` という集計行が出ます。対象 layer がなければこの行は出ません。このログは P1A の使用状況を示し、FL=3 と既定 variant のどちらを選んだかは示しません（`engine/src/prefill/prefill.cpp:2273-2308,5857-5861`）。

この変数の設定による性能値は、条件を揃えた Strata の資料で確認できません。実装コメントにある FL=3 と FL=0 の比較値は P1A カーネル選択の注記ですが、本調査では個別測定として扱いません（`engine/src/prefill/moe_p1a.cu:521-522`）。

## 根拠

- `engine/src/prefill/moe_p1a.cu:509-556` — 型 pair、環境変数の判定、GPU fallback、kernel variant の起動。
- `engine/src/prefill/moe_fused_iq.cu:68-72,3612-3629,3656-3714` — P1A 有効化条件、入力状態、適用条件、起動失敗時の扱い。
- `engine/cmake/backends/hip.cmake:30-46` — P1A ソースの HIP backend への組み込み。
- `engine/src/prefill/prefill.cpp:2273-2308,5857-5861` — P1A 使用状況の集計ログ。
