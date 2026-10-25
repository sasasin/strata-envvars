# `--stats`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンのトップレベル引数） |
| オプション | `--stats` |
| 別名 | なし |
| 値 | 取らない真偽フラグ |

## 役割

通常の生成・serve 実行が計測サマリーまで到達したとき、トークン時間、CPU expert pool、expert 読み込み数などの統計を標準出力に追加します。フラグ自体は `Options::stats` を有効にし、計測値の表示を切り替えます。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --stats
```

これはエンジンの引数形式の例です。実際に使う pack と token ID は実行環境に合わせてください。ソースの usage 表記は `strata generate --pack DIR --tokens ... [options]` です。

## 値と既定値

- 値は不要で、指定すると `o.stats = true` になります。既定値は `false` です。
- 重複指定は同じ真偽値を再設定するだけです。
- `--stats=true` のような値付き形式は定義されていません。通常の parser では未知引数として扱われ、usage を表示して終了コード `2` になります。
- `--tokens` など別の必須条件や他オプションの validation は独立して適用されます。`--stats` 自体に個別の値 validation はありません。

## 実行時の動作

`--stats` が有効で最終レポートに到達すると、標準出力に次の項目を表示します。

- 実時間ベースの ms/token と、計測できている場合は PLE・embedding・layers・head・readback・sampling の内訳
- CPU expert pool の時間と dispatch 数、pool 内の wait/drain/re-park 内訳
- expert blob 読み込み数
- 条件に応じて remote expert、expert cache、elastic K/V、token graph、captured graph/ring の統計

値はそのプロセス内の実行で集計されたカウンターに基づきます。表示ブロックは `o.stats` で囲まれています。`--stats` の参照はこの最終表示条件だけで、ファイル出力や別プロセス起動を行いません。出力される内容の一部は、利用中の機能が有効である場合に限られます。

## 適用条件と副作用

- 通常のエンジン経路では、`--stats` は生成処理の計算設定を変更せず、サマリー行を stdout に追加します。`stdout` は main の冒頭で unbuffered に設定されています。
- `--gpu-stages`、`--graph-only`、`--gpu-only-full` はそれぞれ統計レポートの位置より前に独自結果を出して `return 0` するため、これらの計測専用経路では `--stats` の最終サマリーは出ません。
- Qwen3.6 の GGUF は parser より前に `src/qwen35/q36_engine.cu` の別実装へ振り分けられます。この実装では通常モードの未知オプションとして `--stats` が usage 表示・終了コード `2` になります。引数列で `--serve` より後に置かれた場合は未知オプションを警告して読み飛ばすため、統計表示は有効になりません。`--serve` より前に置かれた場合は通常モードの未知オプションとしてエラーになります。
- `--stats` 固有のファイル書き込み、ネットワーク通信、GPU 操作はありません。エンジン本来の生成・serve の副作用はこのオプションの作用ではありません。

## 出力とエラー

通常経路のレポートは `std::printf` による stdout 出力です。実行が途中でエラー終了し、レポート位置まで到達しない場合は統計サマリーも出ません。`--stats` 自体に独立したエラー経路や終了コードの変更はありません。未知引数となる別実装・値付き形式のエラーは stderr に出力され、終了コード `2` です。

## 根拠

- `src/program/generate.cpp:418-600` — `Options` のメンバー。`stats` の既定値は `false`。
- `src/program/generate.cpp:806-810,972-980` — usage の呼び出し構文と `--stats` の help 説明。
- `src/program/generate.cpp:2413-2424,2778-2793` — 引数 loop、値を取らない parser 分岐、未知引数時の stderr・usage・終了コード `2`。
- `src/program/generate.cpp:7137-7148,7285-7312,7325-7355` — `--gpu-stages`、`--graph-only`、`--gpu-only-full` の独立出力・早期終了経路。
- `src/program/generate.cpp:16926-17027` — `o.stats` によるレポート出力、条件付き内訳、後続の終了処理。
- `src/program/generate.cpp:2393-2407` — 対象モデルを Qwen3.6 実装へ振り分ける経路。
- `src/qwen35/q36_engine.cu:3735-3795` — Qwen3.6 側の parser。通常モードの未知引数拒否と serve モードの未知 `--` オプション無視。

調査時点の Strata checkout は `main...origin/main` で未コミット変更なしでした。ビルド済み CLI の `--help` は実行していません。
