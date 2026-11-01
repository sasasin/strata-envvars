# `STRATA_GRAPH_PRIO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA verify window graph の kernel node に、capture 元 stream の優先度を保持させる opt-in です。設定すると、Strata が作成する window 用 `cs_` / `side2_` stream を中間優先度、`side_` stream を高優先度、共有 expert 用 `sh_cs_` stream を低優先度で作成し、graph の instantiate に `cudaGraphInstantiateFlagUseNodePriority` を指定します。外部から渡された `cs_` stream はこの箇所では作成・優先度設定されません。`side_` と `sh_cs_` の処理自体をこの変数が有効化するわけではなく、各処理は既存の分岐条件が満たされたときだけ graph に入ります（`src/core/verify.cpp:1055-1069,1072-1093,1112-1116,1159-1167,1520-1544,1828-1836,2048-2051,2171-2174,2718-2725`）。

## 値と判定

値は `std::atoi()` で変換し、結果が 0 以外なら ON とします。文字列全体の妥当性検査はありません。

| 環境変数の値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | `atoi("")` が 0 となるため OFF |
| 数値変換結果が 0 | OFF。例: `0`, `0abc`, 数字で始まらない文字列 |
| 数値変換結果が 0 以外 | ON。例: `1`, `-1`, `2`, `1abc` |

先頭の空白や符号を含む文字列も `atoi` の変換規則に従います。境界外の整数文字列については、このコードが個別の検証や fallback を実装していません（`src/core/verify.cpp:220-226`）。

## 有効になる条件

- `STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` のいずれかを定義した build では、helper が常に `false` を返すため、この環境変数では有効になりません（`src/core/verify.cpp:220-227`）。
- それ以外の build でも、device の stream priority range の取得に成功し、`gp_lo != gp_hi` の場合にだけ優先度付き stream を作成します。range が `0..0` など幅を持たない場合、graph priority の要求が ON でも stream は通常の優先度で作られます。range 取得失敗時は CUDA error を読み捨てます（`src/core/verify.cpp:1060-1069,1086-1093`）。
- `side_` と `side2_` の stream は `g_side_mixer() > 0` の場合だけ作成されます。GDN gate / QSA indexer の `side_` branch は `sidem` 条件、gate projection / QSA query の `side2_` branch は `side_proj` 条件に依存します（`src/core/verify.cpp:1159-1167,1234-1237,1538-1561,1828-1844`）。
- 共有 expert 用 `sh_cs_` は初期化されますが、共有 expert の並行 branch は `sh_stream_on()`、profile 状態、stream/event の利用可否などで決まる `sh_fork` が真の場合にだけ使われます（`src/core/verify.cpp:1112-1116,2048-2051,2160-2174`）。
- `STRATA_PIPED_CONCURRENT` が非ゼロで、かつ `STRATA_PIPED_CONCURRENT_PRIO` が未設定または `atoi` の結果が非ゼロなら、共通の stream 作成 helper は device の最高優先度で stream を作成して先に戻ります。この場合、helper を使う `copy_`、Strata 作成の `cs_`、`sh_cs_` では `STRATA_GRAPH_PRIO` が指定する個別の優先度よりこちらが優先されます。`STRATA_PIPED_CONCURRENT_PRIO=0` ならこの優先経路は使われません。`side_` / `side2_` は別の作成経路です（`src/core/verify.cpp:1072-1093,1112-1116,1159-1164`）。
- 優先度付き stream の作成に失敗すると、そのエラーを読み捨てて通常優先度の stream 作成へ進みます（`src/core/verify.cpp:1086-1093`）。

## 実行時の詳細

`graph_prio_on()` の結果は関数内の `static const bool` に保存されます。最初の呼び出し時に環境を読み、その後プロセス内で環境変数を変更しても再評価しません。最初の呼び出しは verifier 初期化中の priority range 判定にあります（`src/core/verify.cpp:220-226,780,1060-1063`）。

window capture 中、優先度付き branch の fork と tail の graph node を記録します。graph を instantiate する前に kernel node の priority を調べ、capture 元 stream の priority が graph に記録されていなければ、記録した fork/tail の依存関係をたどって kernel node の priority attribute を設定します。その後 `cudaGraphInstantiateFlagUseNodePriority` を渡して graph を instantiate します（`src/core/verify.cpp:1238-1242,1543-1544,1835-1836,2052-2054,2132-2136,2171-2174,2718-2725,4168-4201,4203-4261`）。

優先度 range が使え、優先度付き stream が成立すると stderr に `strata verify: STRATA_GRAPH_PRIO: stream priorities ...` が出ます。window graph の capture ごとに kernel node の priority histogram と capture / repair の結果も stderr に記録します。capture note や node attribute の取得・設定に失敗した場合は一部の CUDA error を読み捨て、priority repair を続行できない場合があります。graph instantiate 自体が失敗すれば通常の `verify: instantiate: ...` エラー経路で capture が失敗します（`src/core/verify.cpp:1062-1069,4171-4200,4206-4258,2725-2727,4264-4304`）。

`docs/DETAILS.md` は CUDA の opt-in decode switch として掲載し、CMP 170HX（sm_80）、Qwen3.8-Flash-Next IQ3_S native pack、`--spec 3`、約 3,000 語の prompt 後の decode という報告者の条件下で `STRATA_QIL=1` 時に decode +1.8% と記載しています。同資料は回答が bit-exact と報告しています。この数値は当該報告条件の値で、他の GPU や設定での性能を示すものではありません（`docs/DETAILS.md:1524-1530`）。

## 根拠

- 読み取り、compile-time guard、cache: `src/core/verify.cpp:220-227`
- 優先度 range、stream 優先度、初期化時のログ: `src/core/verify.cpp:1055-1093,1112-1116`
- priority branch の作成条件と利用箇所: `src/core/verify.cpp:1159-1167,1234-1242,1538-1544,1828-1844,2048-2054,2160-2174`
- capture priority の記録、node の補正、graph instantiate flag: `include/strata/core/verify.hpp:473-482`; `src/core/verify.cpp:2718-2727,4168-4261`
- Strata の測定資料: `docs/DETAILS.md:1524-1530`
