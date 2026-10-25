# `--vram-reserve-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。parser は `int` に `std::atoi` で変換する |

## 役割

expert cache の自動サイズ計算で、重み・セッション等を読み込んだ後に GPU 上で空けておく VRAM の量を指定します。主にグラフ、prompt 用領域、draft head など後続の GPU 割り当てに余地を残すための設定です。既定値は 700 MiB です（`src/program/generate.cpp:609-612`）。

## 使い方

```sh
strata --pack ./model.gguf --expert-cache auto --vram-reserve-mib 1200 --serve
```

`--expert-cache auto` は残り VRAM から cache slot 数を決めます。明示値 `1200` はその計算で確保する余白を 1200 MiB にします。エンジン引数は `src/program/generate.cpp` の root parser が処理します（同ファイル `2413-2425`, `2571-2573`）。

## 値と既定値

- 値は必須です。直後の引数がない場合は `--vram-reserve-mib needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。
- 既定値は `700` MiB です。指定すると `std::atoi` の結果が設定され、コマンドラインで指定済みであることを示すフラグも立ちます（`src/program/generate.cpp:611-612,2571`）。
- `atoi` による変換で、専用の範囲・形式検証はありません。数値として読めない文字列は 0 として扱われ、数値の後ろに余分な文字がある場合も parser 側では拒否されません。負数も拒否されません。
- 同じオプションを複数回指定した場合、引数を順に処理して値を上書きするため、最後の指定が残ります（`src/program/generate.cpp:2416-2421,2571`）。

## 実行時の動作

通常の expert cache 自動サイズ計算では、空き VRAM から reserve、prompt buffer の見積もり、draft head 等の領域を差し引き、残量を expert slot の blob サイズで割って slot 数を求めます。profile がある場合は profile の件数も上限になります。算出した slot 数と reserve は stderr に表示されます（`src/program/generate.cpp:6017-6023,6100-6116,6130-6133`）。

相互作用・条件:

- Windows の HIP build では、auto cache を使い、GPU の総容量が 15 GiB 以上で、reserve をコマンドライン指定していない場合、reserve を 2560 MiB に引き上げます。このとき stderr に補正内容を表示します。明示指定がある場合はこの補正をしません（`src/program/generate.cpp:6081-6098`）。
- 自動サイズ計算で必要な最小 cache slot 数に届かず、値が未指定なら、300 MiB 以上の範囲で reserve を縮めて slot を確保する場合があります。明示指定時にはこの縮小を行わず、cache slot が 0 なら不足量と対処案を stderr に表示します（`src/program/generate.cpp:6164-6203`）。
- layer split で cache 数が reserve 等と両立しない場合、cache 数を実際に収まる数まで下げ、警告します（`src/program/generate.cpp:6204-6219`）。
- `--vram-elastic` を有効にした serve では、サーバーの `VRAM` コマンドで値を省略したとき、この option の開始時 reserve が目標値になります。`VRAM N` は cache の segment を縮小・再拡張して N MiB を空けようとします。これは `--vram-elastic` の有効化が必要で、resident low-RAM mode、`--peer-device`、prompt loan 中などは拒否されます（`src/program/generate.cpp:11197-11205,11221-11237`）。
- `--vram-reserve-later-mib` は layer split の後続 GPU 用の別設定です。未指定時はこの option の値を後続 GPU の診断基準に使います（`src/program/generate.cpp:617-619,11036-11049`）。
- 手動 `--expert-cache N` を含む他の構成でも、reserve は一部の sizing・診断や失敗時の案内に参照されます。たとえば CUDA cache allocation 失敗時は reserve を増やす案内を返し（`src/core/expert_source.cpp:6150-6155`）、prefill の変換 buffer が確保できない場合は reserve を増やす等の案内を出して終了コード 1 になります（`src/prefill/gemm.cu:1053-1059`）。

## 適用条件と副作用

この値は GPU memory allocator にその量を直接確保させる指定ではなく、主に expert cache の容量計算で残しておく目安です。したがって、GPU 上で他プロセスが使用する VRAM や後続処理の実割当量を保証しません。serve 中の request 開始時に空き VRAM が安全域を下回ると、エンジンは低空き容量の警告を出し、reserve を増やすか context/batch を下げる案内をします（`src/program/generate.cpp:12034-12049`）。

`--vram-elastic` と組み合わせた serve の `VRAM` 操作では、expert cache の縮小により退避した expert は cache miss 扱いとなり、prompt path の cache slot loan / chunk も残量に合わせて調整されます。操作後は reserve、slot 数、空き VRAM 等を stderr と stdout に出力します（`src/program/generate.cpp:11197-11220,11302-11315`）。

## 出力とエラー

- 引数値の欠落は stderr のエラーと終了コード 2 です（`src/program/generate.cpp:2418-2420`）。
- reserve の形式や範囲に対する専用エラーは parser にありません。負数・不正形式を指定した場合の下流計算の扱いはこの option の宣言箇所では制限されていません。
- auto sizing の reserve 補正、reserve に対して slot が不足するケース、または VRAM 不足時の警告は stderr に出ます（`src/program/generate.cpp:6088-6097,6174-6202,6130-6133`）。
- `VRAM` コマンドで reserve が負数、または数値がない指定は `expected: VRAM [reserve_mib]` として操作失敗になります。elastic 未使用などの適用条件違反も個別エラーになります（`src/program/generate.cpp:11221-11237`）。
- CUDA cache allocation の失敗では、上位処理がエラーを返し、reserve を増やす案内が含まれます（`src/core/expert_source.cpp:6150-6155`）。この文書では特定 GPU・driver・build の実際の割当成否を検証していません。

## 根拠

- Strata revision と作業ツリー: `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`（変更表示なし）。
- 索引の scope は `docs/cli/README.md:1128-1135`。対象 option は通常 engine の root options として `docs/cli/README.md:1307-1310` に掲載されています。Qwen3.6 専用 parser は別 scope として索引化されています（同 `1318-1322`）。
- parser、既定値、自動 reserve / cache sizing、serve の動的制御: `src/program/generate.cpp:609-619,2416-2425,2571-2573,6017-6035,6081-6133,6164-6219,11197-11237,11302-11315`。
- allocation・prefill buffer の失敗案内: `src/core/expert_source.cpp:6150-6155`, `src/prefill/gemm.cu:1053-1059`。
- request 時の空き VRAM 警告: `src/program/generate.cpp:12034-12049`。

調査は指定 commit のソースと索引に基づきます。CLI help、build 生成物、GPU/driver ごとの境界挙動は実行していません。
