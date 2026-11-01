# `strata-dsv41 --experts`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 engine の root CLI） |
| オプション | `--experts` |
| 別名 | なし |
| 値 | `N`（整数相当）または `auto` |

## 役割

DeepSeek-V4.1 の通常層で、各 token の routing に使う expert 数を指定します。モデルが本来選ぶ数より小さくすると router の上位 `N` 件を使い、選択された expert の重みは再正規化されます。モデル本来の expert 数まで指定すると全数を使います（`src/dsv41/ds4_model.hpp:49-51`; `src/dsv41/ds4_experts_rule.hpp:1-6`; `src/dsv41/ds4_model.cu:2361-2380`）。

## 使い方

モデル pack の通常実行に指定する例です（pack の場所や token ID は手元のモデルに合わせます）。

```sh
strata-dsv41 --pack ./model/maya-ds4 --ids 123,456 --experts 5
```

engine CLI の usage は `--experts N|auto` としており、`--pack` と実行モード（例では `--ids`）も必要です（`src/dsv41/ds4_main.cpp:101-109,1395-1400`）。

## 値と既定値

- `N` は正の expert 数として扱われ、parser は `std::atoi` の結果を最低 `1` に丸めます。`0`、負数、整数に変換できない文字列は `1` になります。整数の後ろに余分な文字がある場合も `atoi` は先頭の数値部分を使います。厳密な構文検査や parser 段階の上限検査はありません（`src/dsv41/ds4_main.cpp:1338-1341`）。
- `N` がモデルの値を超える場合、実効値はモデルが元々使う expert 数までに制限されます（`src/dsv41/ds4_experts_rule.hpp:39-46`）。モデルの元の数は pack metadata `num_experts_per_tok` から読みます（`src/dsv41/ds4_model.cu:512-519`）。
- 未指定時と `auto` は同じ自動選択です。現在の通常ルールでは、使用 GPU の合計 VRAM が 16 GiB 以下、統合 GPU がある、または条件を満たす複数 RDNA4 GPU のいずれかなら 5（モデルの元の数が 5 未満ならその数）、それ以外はモデル本来の数を使います（通常の DeepSeek-V4.1 pack では 6）。`DS4_DEFAULTS=026` / `0.2.6` / `v0.2.6` の場合は複数 RDNA4 条件を無効にし、小容量 VRAM・統合 GPU の条件だけで自動選択します（`src/dsv41/ds4_experts_rule.hpp:22-46`; `src/dsv41/ds4_model.cu:2361-2372`）。
- 同じオプションを複数回指定した場合、parser は出現ごとに値を代入するため最後の指定が残ります（`src/dsv41/ds4_main.cpp:1307-1341`）。

## 実行時の動作

parser は未指定を `-1`、`auto` も `-1` として保存します。モデル読み込み時、最初の通常層で GPU の総 VRAM、統合 GPU の有無、複数 RDNA4 GPU の条件を使って自動値または明示値を決め、その値を後続の通常層にも適用します。各層の expert 数はモデル本来の数と選択値の小さい方です（`src/dsv41/ds4_main.cpp:1338-1341`; `src/dsv41/ds4_model.cu:2353-2380`）。

選択数がモデル本来の数より少ないときは、その上位数の expert を routing に使い、選ばれた expert の routing weights を再正規化します（`src/dsv41/ds4_experts_rule.hpp:1-6`; `src/dsv41/ds4_model.cu:8352-8361,10424-10425`）。このため `--experts` は診断表示だけでなく推論計算を変えます。

`DS4_TOPK` が設定され、`atoi` で得た値が `1` からモデル本来の expert 数までの範囲なら、環境変数が `--experts` と自動ルールの結果を上書きします。これはソースコメントでテスト用とされている override です（`src/dsv41/ds4_experts_rule.hpp:157-164`; [環境変数 `DS4_TOPK`](../../../envvars/DS4_TOPK.md)）。

## 適用条件と副作用

- この option は独立 engine CLI `strata-dsv41` の引数です。CMake では `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` でない場合に target が生成されます（`CMakeLists.txt:909-918`）。
- router の expert 数を減らすと出力品質や計算量も変わり得ます。ソースは expert 選択数と routing weights の変化を示しますが、特定環境での速度・品質の改善量はこの調査では測定していません。
- `DS4_TOPK` による上書きがあっても、stderr の説明文は `--experts` の明示指定有無を基準に選ばれます。そのため括弧内の `as asked` / `faster mode` は実際の最終値の出所を示さない場合があります（`src/dsv41/ds4_model.cu:2372-2378`）。

## 出力とエラー

選択値がモデル本来の数より少ない場合、モデルロード時に stderr へ `ds4: experts per word: N (...)` を出します。全数を使う場合、明示的な `N` が指定されていれば `ds4: experts per word: N (full quality)` を出します。未指定または `auto` で全数となった場合は、この option に関する行を出しません（`src/dsv41/ds4_model.cu:2372-2378`）。

値の範囲外を理由に失敗する validation はありません。値を省略すると parser は stderr に `--experts needs a value` を出して終了コード `2` で終了します。未知の option は stderr に `unknown option ...` と usage を出し、終了コード `2` です（`src/dsv41/ds4_main.cpp:1309-1314,1379-1385`）。値は受理されても pack のロードが失敗した場合は `maya-ds4: <理由>` を stderr に出して終了コード `1` になります（`src/dsv41/ds4_main.cpp:1402-1407`）。

## 根拠

- `src/dsv41/ds4_main.cpp:101-109` — CLI usage と値の表記。
- `src/dsv41/ds4_main.cpp:1307-1341,1382-1407` — parser、値変換、missing value / unknown option / load error の経路。
- `src/dsv41/ds4_model.hpp:49-51` — option の保存先と未指定時の内部値。
- `src/dsv41/ds4_experts_rule.hpp:22-46,157-164` — `DS4_DEFAULTS` を含む自動選択、上限補正、テスト用 `DS4_TOPK` override。
- `src/dsv41/ds4_model.cu:512-519,2353-2380,8352-8361,10424-10425` — pack の expert 数、通常層への適用、router 呼び出し。
- `CMakeLists.txt:909-918` — engine target の build 条件。

調査範囲は上記 commit のソースと既存の環境変数文書です。同一 revision の engine binary による `--help` は実行していません。数値 parse は C/C++ の `atoi` を使うため、空文字や不正形式など個々の文字列の細かな変換結果はソースの変換規則を超えて保証せず、GPU/backend ごとの実測挙動も確認していません。
