# `--cpu-threads`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41` |
| オプション | `--cpu-threads` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 `N` |

## 役割

GPU VRAM に載らず CPU lane で処理する routed expert 向け worker pool の大きさを制御します。全体の推論スレッド数や GPU のスレッド数を直接指定するオプションではありません。CPU lane の pool は NUMA node ごとに作られます（`src/dsv41/ds4_model.cu:2620-2625,4624-4626`）。

## 使い方

```sh
strata-dsv41 --pack /path/to/maya-ds4 --cpu-threads 8 --ids 1,2,3
```

`--pack` と推論入力 `--ids` を指定する通常実行例です。`strata-dsv41` は `STRATA_BUILD_DSV41=ON` の build で生成される独立 executable です（`CMakeLists.txt:798-809`）。

## 値と既定値

- 値は必須です。値を省略すると `--cpu-threads needs a value` を標準エラーに出し、終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1200-1207,1215`）。
- 既定値は `Options::cpu_threads = 0` です。未指定、または指定値が `0` 以下の場合は pool 数の明示的な上限制御に入らず、自動設定側の処理になります（`src/dsv41/ds4_model.hpp:25-32`, `src/dsv41/ds4_model.cu:4650-4654`）。
- parser は `std::atoi` を使い、正の範囲や数値形式を別途検証しません。そのため不正な数値文字列をエラーとして拒否する処理は見つかりません。重複指定は parser が順に代入するため、後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1207,1215`）。

## 実行時の動作

値は `Options` に保存され、モデル読み込み時に作成する CPU pool の worker 数の計算に使われます。正の値では NUMA node 数 `NH` ごとの上限を `N / NH` に基づいて求め、最初の pool についてはさらに 1 を差し引きます。各 pool の実 worker 数を既存の core 数以下に制限し、最初の pool は 0 worker、他の pool は最低 1 worker となるよう計算します（`src/dsv41/ds4_model.cu:4626-4654`）。このため `N` は単純に「必ず N 本起動する」という指定ではなく、core 数や NUMA 分割に応じた上限です。

0 以下（未指定を含む）では、core 構成に基づく自動値を使います。CPU lane が全 logical CPU を使う構成の場合、既定では最初の pool 用 core から 2 個を空ける処理があります。この空きを適用する条件は「`--cpu-threads` が正でない」「lane が logical CPU を使い切る」「対象 pool に余裕がある」場合です。環境変数 `STRATA_DS4_LANE_FREE` はこの自動時の空き数を変更します（未設定時 2、値は 0 以上に丸める。`src/dsv41/ds4_model.cu:4633-4654`）。

モデルの説明出力には CPU lane の routed expert 数、配置量、および実際の pool thread 数が含まれます（`src/dsv41/ds4_model.cu:4435-4453,4619-4622`）。

## 適用条件と副作用

効果があるのはモデルを読み込んで CPU pool を作る経路です。`--serve`、通常推論、score/profile 等はモデル読み込み後に分岐するため、この設定を受け継ぎます（`src/dsv41/ds4_main.cpp:1275-1301`, `src/dsv41/ds4_model.cu:2620-2639`）。`--pack-info` と `--version` はモデル読み込み前に終了するため、worker pool を作りません（`src/dsv41/ds4_main.cpp:1251-1254,1275-1281`）。

CPU lane の expert がない場合に pool の存在や起動数がどう最適化されるかは、このオプションの parser だけからは断定できません。値自体はモデル読み込み処理に渡され、CPU lane の pool 設定に使われます。実際の thread 数は core 検出、NUMA 分割、GPU に配置された expert 数などにも依存します（`src/dsv41/ds4_model.cu:3919-3967,4624-4654`）。

## 出力とエラー

- 値を省略した場合は parser が標準エラーに不足を出し、終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。
- 未知のオプションは標準エラーに `unknown option ...` と usage を出し、終了コード `2` です（`src/dsv41/ds4_main.cpp:1266-1273`）。
- CPU thread 数の指定範囲を理由に失敗させる validation 経路は確認できません。モデルの読み込みに失敗した場合は `maya-ds4: <理由>` を標準エラーに出し、終了コード `1` になります（`src/dsv41/ds4_main.cpp:1289-1294`）。

## 根拠

- parser と必須値の取得: `src/dsv41/ds4_main.cpp:1200-1207,1215`
- 既定値: `src/dsv41/ds4_model.hpp:25-32`
- NUMA pool の作成条件・既定時の core 空き・正値の worker 数計算: `src/dsv41/ds4_model.cu:2620-2639,4624-4662`
- CPU lane と routed expert 配置の説明出力: `src/dsv41/ds4_model.cu:4435-4453`
- ヘルプ、未知 option、モデル読み込み前後の分岐: `src/dsv41/ds4_main.cpp:85-94,1251-1301`
- executable の build 条件: `CMakeLists.txt:798-809`

調査範囲はこの checkout のソースです。Release artifact の配布状況や実機での thread 数・性能差は確認していません。
