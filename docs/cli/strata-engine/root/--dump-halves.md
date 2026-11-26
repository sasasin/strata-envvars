# `--dump-halves`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（索引上の配置: `root/`。`strata-terminal` ではない） |
| オプション | `--dump-halves` |
| 別名 | なし |
| 値 | 出力ファイルのパス (`PATH`) |

## 役割

モデルの各 layer について、attention 側と MoE 側の block output および injection vector をホストへコピーして、生成位置ごとにファイルへ追記します。layer 間の差異を調べるための診断ダンプです。実装上は QSA の中間データも同じ記録に含まれます。

## 使い方

```sh
# 1 位置分を /tmp/halves.f32 に記録する（MODEL.gguf は使用するモデルに置き換える）
strata generate --pack DIR --tokens "1,2,3" --max-new 1 --dump-halves /tmp/halves.f32
```

`DIR` は使用する pack directory に置き換えます。エンジンの usage はこの `strata generate --pack DIR --tokens ...` 形式を示しています (`engine/src/program/generate.cpp:1208-1212`)。

## 値と既定値

- `PATH` は値を取る必須引数です。専用の形式・範囲検証はなく、文字列をそのまま出力先パスとして保持します。値を省略すると `--dump-halves needs a value` を stderr に出し、終了コード 2 で終了します (`engine/src/program/generate.cpp:3842-3847,3897`)。
- 未指定時は空文字列のままで、ダンプファイルを作りません。オプションを複数回指定すると代入が繰り返され、最後の値が使われます。空文字列を最後に渡した場合は空値判定によりダンプが無効になります (`engine/src/program/generate.cpp:3897,6184`)。
- 出力は生成位置ごとに `n_layers * half_stride` 個の float を順に書きます。`half_stride` は `2*n_embd + 2*hc + n_head*head_dim + 5*n_head_kv*head_dim + 8` で、ヘッダーや型情報は付かない生データです (`engine/src/program/generate.cpp:6179-6181,24334-24338`)。
- layer 内の配置は、2つの half の `block_out`、2つの `inject`、QSA pre-gate attention、QSA raw vcur、gathered v_scratch、4個の id と4個の step、v_pool prefix、post-norm 後の post-rope kcur の順です。全要素を float 領域として確保し、QSA の一部領域は fp16 ペアを float 領域へコピーします (`engine/src/core/layer.cpp:1453-1470`)。各 half のデータはそれぞれの block output / injection の位置へ非同期 device-to-host copy されます (`engine/src/core/layer.cpp:1472-1480,1569-1571,1637`)。

## 実行時の動作

パーサは受け取ったパスを `Options::dump_halves` に格納します (`engine/src/program/generate.cpp:839,3897`)。実行時にパスが空でなければ `PATH` を `wb` モードで開き、layer 数と stride に応じたホスト staging buffer を確保して `ss.block.dump` に設定します (`engine/src/program/generate.cpp:6174-6195`)。half のコピーは layer graph の capture 中に登録され、生成位置ごとの layer 処理後に staging buffer 全体をファイルへ書き込みます (`engine/src/core/layer.cpp:1453-1457`; `engine/src/program/generate.cpp:24334-24338`)。

この capture のタイミングが必要なため、`--no-capture` と併用すると実行開始前の検査でエラーを出し、終了コード 2 で拒否します (`engine/src/program/generate.cpp:10582-10586`)。`--dump-halves` が有効な場合は `--gr-native-mmvf` が有効でも fused GR を使わない条件になります (`engine/src/program/generate.cpp:6112-6113`)。

## 適用条件と副作用

- 出力先は `fopen(..., "wb")` で開くため、同名ファイルがあれば切り詰めます。書き込み可能なパスが必要です。開けない場合は `strata generate: cannot write PATH` を stderr に出し、終了コード 1 で戻ります (`engine/src/program/generate.cpp:6184-6188`)。
- staging buffer は全 layer 分の pinned host memory です。確保に失敗すると `strata generate: cannot pin the half-dump staging buffer` を stderr に出し、終了コード 1 で戻ります (`engine/src/program/generate.cpp:6190-6194`)。
- 各位置の `fwrite` と終了時の `fclose` の戻り値は確認されていないため、出力途中の書き込み失敗をこの経路が検知・報告する処理は確認できません (`engine/src/program/generate.cpp:24334-24338,25389-25394`)。
- 正常終了処理ではファイルを閉じて staging buffer を解放し、stdout に `halves dumped` とパス、layer 数、1位置あたりの stride を表示します (`engine/src/program/generate.cpp:25389-25394`)。
- SYCL 実装にも同じ option の parser、capture 制約、ファイル出力があります (`engine/sycl/src/program/generate.cpp:1936,3308-3330,5995-5999,13545-13549,14367-14371`)。ただし CUDA/SYCL の実行環境ごとの出力値や実行条件の差は、このソース調査だけでは比較していません。

## 根拠

- `engine/src/program/generate.cpp:836-845,1285-1289,3894-3898` — option の説明、値の保持、help 表示、parser 登録。
- `engine/src/program/generate.cpp:3842-3847` — 引数値の取得と省略時の終了経路。
- `engine/src/program/generate.cpp:6112-6113,6174-6195,10582-10586,24334-24338,25389-25394` — fused GR との相互作用、ファイルと staging buffer の準備、capture 条件、位置ごとの書き込み、正常終了時の後始末と表示。
- `engine/src/core/layer.cpp:1453-1480,1569-1571,1637` — stride 内の配置、非同期コピー、各 layer half からの記録箇所。
- `engine/sycl/src/program/generate.cpp:1936,3308-3330,5995-5999,13545-13549,14367-14371` — SYCL 実装の対応箇所。
