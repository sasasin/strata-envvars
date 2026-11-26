# `STRATA_PF_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt 処理で fused MoE expert カーネルを使うとき、1 回のカーネル launch にまとめる expert 数の上限を指定する。未設定時は 128。設定値を 128 より大きくしても、native kernel が wide batch に対応していなければ実効上限は 128 のままになる。対象は launch の分割幅であり、expert の並び順や計算式を選ぶ設定ではない。ソースコメントは同じ行を処理するので出力 bit は同じと説明している（`engine/src/prefill/prefill.cpp:5784-5787`）。

読み取り箇所は prompt の MoE layer 処理中にある `pf_batch` の初期化 1 箇所である。`fused_l` の経路に入った場合にだけ初回評価され、値はプロセス内の関数 static に保存される（`engine/src/prefill/prefill.cpp:5698-5703, 5788-5794`）。

## 値と判定

`std::getenv` で取得し、設定されていれば `std::atoi` で整数化する。`atoi` の変換結果が正のときだけ採用し、0 以下または数値に変換できない文字列は既定値 128 に戻す。その後、ビルド定数 `kBatchRoom` まで clamp する（`engine/src/prefill/prefill.cpp:5788-5792`）。

| build 条件 | unset / 無効値 | 正の値 | 上限 |
|---|---|---|---:|
| HIP、gfx906、または `STRATA_EXPERIMENTAL_SM60` build | 128 | `1` 以上 | 128 |
| 上記以外 | 128 | `1` 以上 | 512 |

空文字は `atoi("") == 0` となり既定値 128。`0`、`0anything`、負数、数値で始まらない文字列も変換結果が正にならないため 128。`atoi` は文字列全体の厳密な数値検証ではなく、先頭の空白や符号を許し、数値の後ろにある非数値部分を無視する（例: `" 16tail"` は 16）。大文字小文字の規則はない。正の値は上表の上限で clamp される。整数変換の範囲外入力に対する独自検査はない（変換は `atoi`）。上限の条件は `engine/include/strata/prefill/moe_fused.hpp:39-48`。

## 有効になる条件

- prompt の該当 MoE layer が fused 経路を選ぶ必要がある。コード上は `use_mmq` または `fused_only`、`stream_all`、peer 処理なし、native layout と対応 format などを使って `fused_nat` を決める。非 native layout では `fused::enabled()` が必要（`engine/src/prefill/prefill.cpp:5691-5703`）。
- 実際に 128 を超える launch 幅を使うには、native fused 経路であること、NVFP4 / MXFP8 の native tensor-core 経路でないこと、`pf_batch > 128`、および `fused::native_wide()` が true であることがすべて必要（`engine/src/prefill/prefill.cpp:5793-5794`）。
- `native_wide()` は NT=256 kernels または warp-specialized kernel が現在の device に設定された場合に true（`engine/src/prefill/moe_fused_iq.cu:3952`）。NT=256 は `STRATA_PF_FUSED_NT=256` または `STRATA_PF_FUSED_F16=1`、warp-specialized は `STRATA_PF_FUSED_WS=1` が要求し、kernel setup の成否も条件になる（`engine/src/prefill/moe_fused_iq.cu:2777-2789, 3007-3021`）。
- HIP、gfx906、`STRATA_EXPERIMENTAL_SM60` build の `kBatchRoom` は 128 のため、`STRATA_PF_BATCH` 自体で 128 超にはならない。その他の build でも wide kernel が未設定なら `per_launch` は最大 128（`engine/include/strata/prefill/moe_fused.hpp:44-48`; `engine/src/prefill/prefill.cpp:5793-5794`）。
- CLI 引数や別の設定値で `STRATA_PF_BATCH` の値を上書きする処理は、この変数の読み取り経路にはない。fused 経路に入らない layer では値を使わず、通常の別 expert 経路に進む（`engine/src/prefill/prefill.cpp:5698-5703, 5862-5864`）。

## 実行時の詳細

値は `fused_l` に入った最初の layer で関数 local static として一度だけ読み込まれ、その後の layer や同一プロセスの後続 prompt で再読込されない。したがって実行中に環境変数を変更しても反映されない。読み取り時点で未設定なら後から設定しても既定値のまま（`engine/src/prefill/prefill.cpp:5707, 5788-5792`）。

実効 `per_launch` を使い、expert ID 順に layer の expert をバッチに分ける。各 batch の expert 数がこの上限に達するか layer の終端に達すると次の launch に進む。stream ring 上の expert 数に応じた分割条件も併用されるため、各 batch が常に上限数になるとは限らない（`engine/src/prefill/prefill.cpp:5793-5805`）。native wide が使えない場合は設定値が大きくても 128 で分割する。

## ログと測定値

この変数の parse、clamp、または採用値を表示する専用ログはない。無効値もエラー終了にはならず 128 に fallback する。別途 NT=256 / warp-specialized を要求したのに setup できない場合は `prefill fused experts (native): STRATA_PF_FUSED_NT=256 is not available here` または `prefill fused experts (native): STRATA_PF_FUSED_WS=1 is not available here` を stderr に出す。その場合 wide は利用できず、batch 幅は最大 128 となる（`engine/src/prefill/moe_fused_iq.cu:3013-3021`; `engine/src/prefill/prefill.cpp:5793-5794`）。wide kernel の launch error は `ck(cudaGetLastError(), "experts_native (NT = 256)")` に渡される（`engine/src/prefill/moe_fused_iq.cu:3990`）。

`docs/DETAILS.md:1817, 1822` は `STRATA_PF_BATCH=N` を「128 超は 256-thread kernels の場合のみ」と記載し、同じ CMP 170HX での prompt +7.6%（4K）、+4.9%（16K）、+4.3%（52K）を掲載する。記載自体が測定者による値で、この箇所にはモデル、量子化、OS、反復回数などの条件が揃っていないため、本調査で再測定・一般化した値としては扱わない。ソースでも 128 超は native wide kernel が使える場合に限る。

## 根拠

- 全参照の直接読み取りと launch 幅の決定: `engine/src/prefill/prefill.cpp:5788-5805`
- fused 経路を選ぶ条件: `engine/src/prefill/prefill.cpp:5691-5703`
- build ごとの batch 上限: `engine/include/strata/prefill/moe_fused.hpp:39-48`
- wide kernel の環境変数と device setup: `engine/src/prefill/moe_fused_iq.cu:2777-2789, 3007-3021, 3952`
- wide launch と失敗経路: `engine/src/prefill/moe_fused_iq.cu:3954-3990`
- 設計資料の説明と測定者注記: `docs/DETAILS.md:1815-1823`
