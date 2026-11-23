# `--spec-nodraft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、root） |
| オプション | `--spec-nodraft` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Hy4 の speculative decode 試験でドラフターを呼び出さず、検証窓に人工候補を与えるためのフラグです。`SpecCfg` では `test only` とされており、通常の生成品質や速度を調整する利用者向け設定ではありません。parser はこのフラグを指定すると `nodraft` と `sabotage` の両方を有効にします (`engine/src/hy4flash/run/hy4_main.hip.cpp:425-428`, `engine/src/hy4flash/run/hy4_spec.hip.h:18-30`)。

## 使い方

ソース上の引数形式に沿った例です。実際に実行すると GPU 推論と出力ファイル作成を伴います。

```sh
strata-hy4 --model model.strata --tokens prompt.ids --draft dfly2 --gen 16 --spec-nodraft
```

## 値と既定値

- 引数値は不要です。`--spec-nodraft` の後ろに値を置く構文はなく、その文字列は別引数として処理されます。
- 未指定時の `SpecCfg.nodraft` は `false`、`SpecCfg.sabotage` は `false` です。指定時は両方 `true` になります (`engine/src/hy4flash/run/hy4_spec.hip.h:18-30`, `engine/src/hy4flash/run/hy4_main.hip.cpp:425-428`)。
- 同じフラグを複数回指定しても同じ真値を代入するだけです。個別の回数検査はありません (`engine/src/hy4flash/run/hy4_main.hip.cpp:375-428`)。
- 数値等の値検証はありません。フラグ自体に値を付ける形式は未定義です。未知の追加引数は `unknown arg ...` を stderr に出し、終了コード `2` になります (`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384`, `498-505`)。

## 実行時の動作

オフライン CLI では `draft` の初期値は `auto` ですが、コメントと分岐上、`auto` は CLI 実行ではドラフターを無効にします。spec 実行モードは `draft == "dfly2"`、`gen > 0`、かつ `--dfly-alloc-only` でない場合に限られます。このため、上の例のように `--draft dfly2` と正の `--gen` を組み合わせないと、このフラグを使った `Spec` の生成経路は動きません (`engine/src/hy4flash/run/hy4_main.hip.cpp:363-365`, `701`, `992-1000`)。

spec ループが検証窓を作る段階で `nodraft` が真なら `d.draft_tree(...)` を呼ばず、系列上に `1000 + j` の候補を組み立てます。その後、同時に有効化された `sabotage` の分岐が候補を擬似乱数列由来の値に置き換え、信頼度を `0.9` に設定します。したがって最終的な検証入力は固定の `1000 + j` ではなく、この sabotage 分岐で置き換えられた候補です。ドラフターによる候補生成を避ける一方、spec 検証と制御器に意図的に悪い候補列を与える試験動作です (`engine/src/hy4flash/run/hy4_spec.hip.h:284-333`)。

`--serve` 経路でも parser から `SpecCfg` が `ServeOpts` に渡されます。serve 側で `draft` が `off` でなく、chunk 条件を満たし DFly2 の初期化に成功した場合に `Spec` を作成して生成で使います。よってこの場合も `--draft off`、小さい chunk、ドラフター初期化失敗では spec 経路は有効になりません (`engine/src/hy4flash/run/hy4_main.hip.cpp:544-570`, `engine/src/hy4flash/run/hy4_serve.hip.h:319-341`, `546-550`)。

## 適用条件と副作用

- 対象は索引で `strata-hy4` とされる CUDA/HIP 実装です。Metal と SYCL は別 parser・別スコープであり、この文書の対象ではありません (`docs/cli/README.md:1277-1283`, `1358-1363`, `1452-1456`; `docs/cli/000_cli_tools.md:11`)。
- `--spec-nodraft` はモデルロード前に drafter を無効化するものではありません。オフラインでは `draft == "dfly2"` のとき `df.init(err)` が先に実行され、serve でも DFly2 の初期化判定が行われます (`engine/src/hy4flash/run/hy4_main.hip.cpp:711-716`, `engine/src/hy4flash/run/hy4_serve.hip.h:319-341`)。
- 検証候補の生成時に GPU 上の検証処理を行います。オフライン spec 実行の完了時には標準出力に `generated ids: ...`、標準エラーに decode 統計が出て、`<out>/gen_ids.txt` を開いて書き込みます。既定の `--out` は `.` なので、同名ファイルがある場合の上書きを避ける実装は確認できませんでした (`engine/src/hy4flash/run/hy4_main.hip.cpp:347`, `992-1017`)。
- `Spec::run` がエラーを返す経路では `spec: ...` を stderr に出して終了コード `1` になります (`engine/src/hy4flash/run/hy4_main.hip.cpp:1000-1005`)。

## 出力とエラー

このフラグ固有の値検証エラーや専用メッセージはありません。未知引数は前述の通り stderr の `unknown arg ...` と終了コード `2` です。spec 実行中のエラーは `spec: ...` と終了コード `1`、成功時は生成 ID と統計を出力します (`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`, `1000-1010`)。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-365` — `draft` と `SpecCfg` の初期値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:401-428` — root parser。`--spec-nodraft` が値を取らず、`sabotage` と `nodraft` を同時に設定する。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数の診断と終了コード。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701`, `711-716`, `992-1017` — オフライン spec モード条件、drafter 初期化、Spec の実行・出力・失敗経路。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30`, `284-333` — 試験用設定、nodraft 時の人工候補生成と sabotage による置換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-570`, `engine/src/hy4flash/run/hy4_serve.hip.h:319-341`, `546-550` — serve への設定転送と spec 利用条件。
- `docs/cli/000_cli_tools.md:11`, `docs/cli/README.md:1277-1283`, `1341` — ツール ID、CUDA/HIP parser scope、および索引上の対象リンク。

## 調査範囲

同一 revision の `--help` は実行していません。ソースの parser と処理経路を確認しました。GPU 実行時の候補値の妥当性や個別 GPU/backend での実測挙動は、この調査では確認していません。
