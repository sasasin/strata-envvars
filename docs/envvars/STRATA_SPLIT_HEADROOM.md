# `STRATA_SPLIT_HEADROOM`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 実装で `--layer-split auto` の配置候補を選ぶ際、予測時間が最速候補に近い候補の中から、各 GPU が担当層の全 expert を置いた後に残す VRAM が最も多い配置を優先します。VRAM を使い切ると Xe ドライバーがバッファをシステムメモリへ移すケースを避けるための選択規則です。モデル計算や expert の順位付けを変える設定ではありません。

この変数は `sycl/src/program/generate.cpp` の自動分割探索でだけ読み取られます。CUDA/HIP 側を含め、リポジトリ内の他の直接参照はありません。

## 値と判定

値の有無ではなく、設定文字列を `std::atoi()` に渡し、変換結果が 0 かどうかで判定します。文字列全体の検証はしません。

| 値 | headroom 選択 |
|---|---|
| 未設定 | 有効 |
| `0`、空文字、`abc`、`true` | 無効（`atoi` の結果が 0） |
| `1`、`-1`、`1abc`、` 1` | 有効（先頭の整数変換結果が 0 以外） |
| `0abc`、`00` | 無効（先頭の整数変換結果が 0） |

大小文字は個別に比較されません。`true` / `false` は真偽値として解釈されず、どちらも `atoi` の結果 0 です。`atoi` が整数に変換できない文字列も 0 になります。

この判定は関数内の `static const bool` に保存されます。自動分割探索で最初に評価された後、同一プロセス内で環境変数を書き換えても再評価されません。未設定時の既定値は有効です。

## 有効になる条件

- `--layer-split auto` が指定され、`--serve` を使用していること。`--layer-split` は serve モード以外では受け付けられません。
- 可視 GPU が複数あり、分割先 GPU が確定して `multi_gpu && split_auto` の探索へ到達すること。
- 複数 GPU の layer split では `--expert-profile` が必要です。
- `--split-skip-if-fits` によって CUDA0 だけで全 profiled pair を保持できると判定されると split 自体が解除され、自動分割探索も実行されません。この場合、変数は効果を持ちません。
- 手動の `--layer-split K[,K2...]` では探索しないため、この変数は参照されません。

実装箇所は SYCL の `sycl/src/program/generate.cpp` です。ここでいう CUDA0 等のログ表記や DPCT API は SYCL エンジン内のデバイス識別・移行コードであり、環境変数が CUDA backend でも動作することを意味しません。

## 実行時の詳細

探索は各 stage の速度と cache に入る expert 数などから各 split の予測 window 時間を計算します。変数が有効なら、候補ごとに `min_spare`（各 stage について、使用可能量から session と担当層の全 expert を差し引いた余裕の最小値）も記録します。最速候補の予測時間を基準に、許容範囲内で `min_spare` が最大の配置を選びます。同じ余裕なら予測時間が短い候補を優先します。

許容範囲は別変数 `STRATA_SPLIT_HEADROOM_TOL` が担い、未設定時は `0.002`（0.2%）です。値は `std::atof()` で変換されます。実装上、負値や 0 は許容幅 0 として扱われ、最速と同じ時間の候補間だけで余裕を比べます。無効な文字列も `atof()` の結果 0 になります。

`STRATA_SPLIT_HEADROOM` が無効なら候補の余裕を記録せず、既存の予測時間による選択を維持します。予測時間の比較は `<` なので、同率最速では探索で先に現れた候補が残ります。選択が元の最速配置から変わったときは stderr に、選ばれた K と元の K、双方の予測時間、余裕を出す `strata generate: layer split auto: K=... instead of K=...` のログが出ます。最終的な自動分割結果は続く `layer split auto: K=... - predicted ...` のログにも出ます。

## 文書と測定値

`docs/INTEL_ARC.md` は、2 枚の Arc Pro B70 と IQ3_S の記載例で、`--layer-split auto` が `K=24`（約 11 tok/s）、手動 `K=30` が約 54 tok/s だったと記しています。同資料は、0.2% 以内の候補から余裕の大きい split を選ぶ説明と、`STRATA_SPLIT_HEADROOM=0` で旧来の選択に戻す説明もしています。これは資料に記載された環境・測定値であり、一般的な性能差を示すものではありません。実装は候補選択とログ出力を確認できますが、この測定自体を再実施していません。

## 根拠

- `sycl/src/program/generate.cpp:2067-2078`: `--layer-split auto` の判定と serve 条件。
- `sycl/src/program/generate.cpp:2121-2125`: 複数 GPU split における `--expert-profile` 必須条件。
- `sycl/src/program/generate.cpp:3237-3255`: `--split-skip-if-fits` で split を解除する経路。
- `sycl/src/program/generate.cpp:3575-3583,3682-3705,3806-3832`: 自動探索条件、環境変数の parse と既定値、候補評価・選択およびログ。
- `include/strata/program/split_rules.hpp:46-74,100-112`: `Placement` の余裕値、許容時間内で余裕を優先する規則、その余裕の算出。
- `docs/INTEL_ARC.md:142-147`: 仕様説明、記載された測定例、`=0` の説明。
