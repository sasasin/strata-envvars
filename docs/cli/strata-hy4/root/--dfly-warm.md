# `strata-hy4 --dfly-warm`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP のオフライン実行） |
| オプション | `--dfly-warm` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

プロンプトの prefill 後、通常の greedy decode を計測・開始する前に DFly2 drafter を一度実行します。ソース内のコメントでは、drafter の各段階のカーネルを先に動かし、その実行後と未実行時の通常 decode を比較するためのテスト用動作とされています。生成の候補を採用する speculative decode を有効にするフラグではありません。

## 使い方

```sh
# DFly2 drafter を初期化し、speculative decode を行わずに warm-up を挟んで生成する
strata-hy4 --model MODEL.strata --tokens ids.txt --gen 16 --draft dfly2 --dfly-alloc-only --dfly-warm
```

`--draft dfly2` は drafter の初期化に必要です。`--dfly-alloc-only` を付けると通常生成経路になり、この経路で `--dfly-warm` が呼ばれます（値はどちらのフラグにも不要です）。モデルには DFly2 drafter tensors が必要です。

## 値と既定値

`--dfly-warm` は parser が見つけると真偽値を `true` にします。引数値を読み取らず、数値範囲などの個別 validation もありません。省略時は `false` で、同じフラグを複数回指定しても同じ真偽値のままです（`engine/src/hy4flash/run/hy4_main.hip.cpp:374-375,435`）。

## 実行時の動作

parser は `dfly_warm` を設定しますが、効果があるのはオフライン実行で `gen > 0` の通常 decode 分岐に入った場合だけです。`--serve` は別の処理へ早期に移り、`--load-only` と dump batch も warm-up 呼び出しより前に終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-612,658-665,701-708,1018-1025`）。

通常 decode 分岐では、prefill の logits から最初の greedy token を選んだ後、decode の時間計測開始前に `dfly_warm && df.ok` を確認します。条件が成立すると `df.rv = 256` とし、`df.draft(T0, next, 7, yy, cc)` を一度呼びます。出力配列 `yy` と `cc` はこの呼び出しだけに使われ、通常 decode は元の `next` から続きます。その後の生成ループでは target model の forward を進め、生成 ID や計測結果を出力します（`engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1058,1075-1104`）。

`df.ok` は DFly2 の `init()` 成功後に立ちます。main 側でこの初期化を行うのは `draft == "dfly2"` の場合です。さらに `spec_mode` は `draft == "dfly2" && gen > 0 && !alloc_only` なので、`--draft dfly2` だけで `--dfly-alloc-only` を付けないと speculative decode 分岐が選ばれ、この通常 decode 内の warm-up 箇所には入りません（`engine/src/hy4flash/run/hy4_main.hip.cpp:701-716,992-1025`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:470-484,569-570`）。

## 適用条件と副作用

- `--draft dfly2` が指定され DFly2 初期化に成功していること、prompt が処理されて通常 decode に進むこと、`--gen` が正であることが必要です。`--draft` の既定値は `auto` ですが、オフライン main は `auto` では DFly2 を初期化しません（既定値と初期化条件: `engine/src/hy4flash/run/hy4_main.hip.cpp:363,701-716`）。
- DFly2 tensors がモデルにない場合や、空き VRAM が 192 MiB 未満の場合、`df.init()` は失敗し main は `dfly2: ...` を stderr に出して終了コード 1 を返します。`dfly-warm` 呼び出しまで到達しません（`engine/src/hy4flash/run/hy4_dfly2.hip.h:470-484`、呼び出し側: `engine/src/hy4flash/run/hy4_main.hip.cpp:712-716`）。
- warm-up の `df.draft()` は GPU 上で DFly2 の draft 計算を試みます。内部の `can_draft()` 条件（anchor の KV 容量、capture された row など）が満たされないと `false` を返します（`engine/src/hy4flash/run/hy4_dfly2.hip.h:578-591`）。
- drafter が拒否した場合は stderr に `dfly warm-up draft refused` を出しますが、この戻り値だけでは main は終了せず、そのまま通常 decode を続けます（`engine/src/hy4flash/run/hy4_main.hip.cpp:1024-1030`）。
- Metal 版の `strata-hy4-metal` および SYCL 版の `strata-hy4-sycl` は別コマンドスコープです。この文書の対象は索引に記載された CUDA/HIP parser のみです（`docs/cli/README.md:1277-1294,1358-1361,1452-1455`）。

## 出力とエラー

warm-up 成功時にこのオプション固有の成功メッセージはありません。拒否時は前述の stderr 警告を出し、通常の生成処理を続けます。通常生成では `generated ids` などが出力され、`--out` のディレクトリに `gen_ids.txt` と `top5.txt` を書きますが、これらは通常 decode に伴う出力です（`engine/src/hy4flash/run/hy4_main.hip.cpp:1075-1109`）。

フラグ名が未知の場合は `unknown arg ...` を stderr に出して終了コード 2 です。`--dfly-warm` 自体に値を付ける構文はありません。フラグの後ろに別のトークンを置くと、そのトークンは独立した引数として処理されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,498-505`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:374-375,435`: フラグの状態と parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:363,701-716,992-1030`: `draft` の既定値、DFly2 初期化、speculative / 通常 decode の分岐、warm-up の呼び出しと拒否時の出力。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:470-484,569-570`: DFly2 初期化条件、VRAM 判定、成功状態。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:578-591`: draft 可否の確認と、不可の場合に `false` を返す処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:1075-1109`: decode 後の表示と出力ファイル。
- `docs/cli/README.md:1277-1294`: `strata-hy4` の階層、CUDA/HIP 実装ファイル、対象 option の索引リンク。
