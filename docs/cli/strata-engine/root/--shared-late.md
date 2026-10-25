# `--shared-late`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンのトップレベル） |
| オプション | `--shared-late` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

MoE 層の shared expert を計算するタイミングを切り替える A/B 用フラグです。通常は GPU が router の後に shared expert を先行計算し、その間にホスト側が CPU expert pool を処理します。このフラグを指定すると shared expert の計算を CPU pool の後にある層後半へ移します。GPU と CPU pool の重なり方を変えるもので、性能向上を保証する指定ではありません。

## 使い方

```sh
strata --native /path/to/model.gguf --tokens 1,2,3 --shared-late
```

`--shared-late` は値を取りません。`generate.cpp` の通常 parser では位置引数の順序に依存せず認識されます。

## 値と既定値

値は不要です。内部値 `shared_late` の初期値は `false` で、指定すると `true` になります。したがって既定では shared expert は早期計算（CPU pool と並行）です。同じフラグを複数回指定しても、同じ真偽値を設定するだけです。専用の値検証やフラグ固有のエラー経路はありません。

## 実行時の動作

通常の `generate.cpp` 経路では、パーサが `o.shared_late` を立て、実行初期化時に `layer_set_shared_early(!o.shared_late)` へ反転して渡します。`block_layer_pre` は早期モードなら router の後に `moe_shared` を実行します。遅延モードではそこで実行せず、`block_layer_post` が CPU pool の結果を受け取った後に `moe_finish` を呼び、その中で shared expert を計算してから routed expert の結果と結合します。従って変わるのは shared expert の計算時点であり、結合処理自体は引き続き行われます。

このフラグはセッション設定 fingerprint に `shared_late` として含まれます。セッション構成の識別に影響します。

## 適用条件と副作用

この切替は `src/core/layer.cpp` の MoE 層処理を通る通常 engine 経路に適用されます。shared expert の重み・テンソル処理や GPU 計算そのものは省略されず、計算の順番が変わります。別オプションとの明示的な排他条件は確認できませんでした。`--native-moe-combine` などを指定した場合も、遅延側の `moe_finish` から共通の結合関数へ進むため、結合実装の選択とは独立です。

ただし、Qwen3.5 系モデルは `generate.cpp` が `strata::qwen35::run` へ委譲します。委譲先 parser に `--shared-late` の分岐はありません。通常の非-serve 実行では未知オプションとして usage を stderr に出して終了コード 2 で失敗します。委譲先 parser がその時点までに `--serve` を受理していれば、未知オプションを stderr に警告して無視するため、この指定による切替は適用されません。

shared expert の実計算では対象重みが欠けている場合や型・量子化データの処理に失敗した場合、`moe_shared` がエラーを返し、層処理も失敗します。これらはフラグ値の検証エラーではなく、shared expert 実行時の失敗です。

## 出力とエラー

このオプションを受理したこと自体による専用出力はありません。通常 parser で未知の引数を渡した場合は `unknown argument: ...` と usage を stderr に出力し、終了コード 2 になります。Qwen3.5 委譲時の未知引数の挙動は前節のとおりです。

## 根拠

- `src/program/generate.cpp:601` — `shared_late` は既定値 `false`。
- `src/program/generate.cpp:888` — help の説明（shared expert を CPU pool の後に置く A/B、既定は pool と重ねる）。
- `src/program/generate.cpp:2416-2424,2778-2792` — 引数 parser、値を要求しない処理、未知引数のエラー。
- `src/program/generate.cpp:3231` — `shared_late` を反転して `layer_set_shared_early` に設定。
- `src/program/generate.cpp:9450-9462` — セッション fingerprint 用 switches に `shared_late` を記録。
- `src/core/layer.cpp:554-555,1570-1574` — 共有 expert の早期計算設定と router 後の実行。
- `src/core/layer.cpp:468-512,531-535,1608-1614` — shared expert の処理・失敗経路と、遅延時に pool 後の `moe_finish` で共有出力を計算して結合する経路。
- `src/program/generate.cpp:2393-2407` — Qwen3.5 系を別実装へ委譲。
- `src/qwen35/q36_engine.cu:3735-3795` — 委譲先 parser にこのフラグがなく、通常の未知引数は終了コード 2、先に `--serve` を処理した後の未知オプションは警告してスキップ。

調査は上記 revision のソースを対象に行いました。別 revision のビルド済みバイナリや Release artifact との照合は行っていません。
