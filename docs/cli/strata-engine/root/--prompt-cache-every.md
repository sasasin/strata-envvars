# `--prompt-cache-every`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root 引数） |
| オプション | `--prompt-cache-every N` |
| 別名 | なし |
| 値 | prompt の新規読み込み token 数を表す整数。既定値 `16384`、`0` は周期 checkpoint 無効 |

## 役割

`--serve` で会話 prompt を読む途中にも、会話状態の checkpoint を定期的に保存します。長い prompt の途中に保存点ができるため、後続リクエストがその位置までと同じ token 列を持つ場合に、prompt の先頭から読み直す範囲を減らせます。エンジンのヘルプも本オプションを `--serve` 用と説明しています（`src/program/generate.cpp:922`）。

## 使い方

```sh
build/strata --serve --prompt-cache-every 4096
```

実際の起動では必要なモデル・pack 関連引数も指定してください。エンジンの usage は `strata generate --pack DIR ...` 形式を示し、serve は `--serve` で有効になります（`src/program/generate.cpp:806-812`、`src/program/generate.cpp:8354`）。

## 値と既定値

- 既定値は `16384` token です（`src/program/generate.cpp:747-748`）。
- parser は次の argv を `std::atoll` で読み、`std::max(0LL, ...)` で負数を 0 に丸めます。strict な数値 validation や範囲エラーはこの parser にはありません（`src/program/generate.cpp:2665`）。整数変換を開始できない文字列は `atoll` の結果 0 となり、周期保存が無効になります。
- 同じオプションを複数回指定した場合は、引数を順に走査するたびに値を代入するため、最後の指定値が残ります（`src/program/generate.cpp:2416-2421`、`src/program/generate.cpp:2665`）。
- 値を省略すると parser は標準エラーに `--prompt-cache-every needs a value` を出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

この値が有効なのは serve の prompt 読み込み経路です。各リクエストの周期閾値は、再利用した位置 `resume` から `N` token 先に設定されます。リクエスト単位で checkpoint を無効にした場合や先頭からの再読み込み診断の場合は閾値を無効化します（`src/program/generate.cpp:13042-13052`）。

prompt の batched prefill が chunk を終えるたびに、読み込み済み位置 `done` が次の閾値以上か確認します。到達した chunk 境界で状態を保存し、次の閾値をその実際の保存位置 `done + N` に進めます。そのため保存間隔は厳密に N token ごとではなく、既存の prefill chunk 境界に合わせて閾値以上へ進む場合があります（`src/program/generate.cpp:9900-9931`）。multi-GPU の layer split では、各 stage が対応位置の checkpoint 部分を保存し、最後の stage が揃った部分をまとめます（`src/program/generate.cpp:9673-9679`、`src/program/generate.cpp:9935-9950`）。

checkpoint は実行中の会話キャッシュに保存されます。`--prompt-cache` が 0 以下なら `checkpoint_at` は保存せず、multi-GPU 経路も部分保存を行いません。保存件数は `--prompt-cache` の上限内で管理され、上限を超えると既存の eviction policy で checkpoint が退避されます（`src/program/generate.cpp:9701-9711`、`src/program/generate.cpp:9829-9855`）。従って本オプションだけでは保存件数・RAM 使用量の上限は決まりません。

`--prompt-cache-tail` は別の追加保存点を選ぶオプションで、既存 chunk 境界、単一 GPU、正の `--prompt-cache` と本オプション値を条件とします。周期 checkpoint の閾値や chunk 分割自体は変えません（`src/program/generate.cpp:923-924`、`src/program/generate.cpp:9907-9931`）。

## 適用条件と副作用

- `--serve` なしでは値自体は parser に受理されますが、この periodic checkpoint 処理は serve のリクエスト処理経路にあるため、単発生成でこの設定による途中保存は行われません（`src/program/generate.cpp:2665`、`src/program/generate.cpp:8354`、`src/program/generate.cpp:9907-9950`）。
- 保存時は GPU 状態を同期し、会話状態をホスト側 checkpoint にコピーします。layer split では各 stage の状態も保存します（`src/program/generate.cpp:9693-9700`、`src/program/generate.cpp:9790-9803`）。そのため有効化すると checkpoint 保存に伴う同期・コピー処理が発生します。性能上の効果やコスト量は機材・モデル・要求に依存し、この調査では測定していません。
- `N=0` は周期 checkpoint を止めますが、会話キャッシュ全体を無効にする指定ではありません。turn 境界など別経路の checkpoint は別途処理されます（`src/program/generate.cpp:9907`、`src/program/generate.cpp:14123-14128`）。

## 出力とエラー

周期 checkpoint の保存に失敗すると、prompt callback が失敗を返し、serve は標準エラーに `strata serve: ...`、標準出力に `ERR ...` を出して終了コード 1 を返します。GPU の CUDA fault が検出された場合は、後片付けで停止することを避けるため `_Exit(1)` を使います（`src/program/generate.cpp:9929`、`src/program/generate.cpp:14107-14118`）。checkpoint コピー失敗の詳細は標準エラーの `strata serve: checkpoint save: ...` に出ます（`src/program/generate.cpp:1732-1736`）。

## 根拠

- option の既定値・serve 用 help: `src/program/generate.cpp:747-748`、`src/program/generate.cpp:922-927`
- parser と値の変換・不足値処理: `src/program/generate.cpp:2416-2421`、`src/program/generate.cpp:2663-2666`
- serve の閾値初期化、chunk 境界での周期保存、multi-GPU の部分保存: `src/program/generate.cpp:9673-9679`、`src/program/generate.cpp:9900-9950`、`src/program/generate.cpp:13042-13052`
- 保存先の bounded cache と `--prompt-cache` 条件: `src/program/generate.cpp:9701-9711`、`src/program/generate.cpp:9829-9855`
- checkpoint 保存処理と失敗経路: `src/program/generate.cpp:1732-1736`、`src/program/generate.cpp:9790-9803`、`src/program/generate.cpp:14095-14128`
- 補助資料（ソース実装と照合）: `docs/DETAILS.md:1144-1145`、`docs/MULTI_GPU.md:388-390`

調査範囲は指定 commit の checkout 内の通常エンジン `src/program/generate.cpp` と関連する同 revision の説明資料です。別 backend の `sycl/src/program/generate.cpp`、ビルド済みバイナリ、公式 Release artifact の実行確認は行っていません。
