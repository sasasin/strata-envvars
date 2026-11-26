# `--prefill-head-alias`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、`strata generate`） |
| オプション | `--prefill-head-alias` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--serve` で動作する単一 GPU の推論サーバーで、プロンプトを読む間だけネイティブ出力 head を VRAM から外し、その領域を prompt workspace として使う。出力 head は decode 前に再ロードされる。VRAM に余裕が少なく、大きな prompt chunk を使いたい場合のための opt-in 機能で、既定では無効。

## 使い方

```sh
strata --pack /path/to/model.pack --serve --mtp auto --short-read 0 --prefill-head-alias
```

このフラグには値を付けない。`--serve`、MTP、`--short-read 0` などの適用条件も満たす必要がある。`--short-read` は通常 64 が既定値なので、この機能を有効にするときは明示的に 0 を指定する。

## 値と既定値

- 値なしの真偽フラグ。parser は指定時に `prefill_head_alias` を `true` にする。省略時は `false`。
- 繰り返し指定は同じ真偽値を再設定する。値・空値を受け取るオプションではない。
- 併用条件の `--short-read` は非負値へ丸められ、既定値は 64。したがって `--short-read 0` が必要。

## 実行時の動作

初期化時に MTP が native output head に bind した後、head を unload し、head のバイト数を stderr に表示する。serve の prompt path では expert-cache のスロットを借り、利用可能な VRAM と借用量から `2048`, `1536`, `1024`, `512` tokens の候補を順に調べ、prompt chunk を選ぶ。prompt path の初期化にも alias フラグが渡される。

リクエストごとに prompt を読む際、head がロード済みなら unload して prompt path を再構築する。prompt 完了後は借りた slot を refill してから head をロードし、decode に戻る。再ロード後に head または scratch のアドレスが前回と異なれば、キャプチャ済み verify window graph を破棄して再キャプチャに備える。head が解放・再取得されるため、prompt workspace と decode 用 head の VRAM 使用時期が切り替わる。

## 適用条件と副作用

起動時に以下を満たさない場合は利用不可として終了する。

- `--serve` が指定されている。
- 複数 GPU / layer-stage ではない。
- `--batch` が正数ではない。
- `--pipeline-windows` が正数ではない。
- `--short-read` が 0。
- `--expert-cache` が `1` または `auto`（省略時の内部値も条件式で許容される）。
- `--mtp` が指定され、native output head がロードされている。

初期化時の MTP bind が失敗すれば起動エラーになる。また、borrowed prompt layout はリクエスト間で relayout できず、prompt 初期化・再構築や head 復元に失敗すると処理を停止する。head の配置アドレスが変わった場合は verify window graph の破棄を試み、破棄に失敗すればエラー終了する。

## 出力とエラー

- 適用条件違反は stderr に `strata generate: --prefill-head-alias is unavailable: ...` を出して終了コード 2。
- 初期 MTP bind の失敗は stderr に理由を出して終了コード 1。
- 初期化時に head を prompt workspace として使うバイト数、serve の選択 chunk / 借用量、head の復元時間などを stderr に記録する。
- リクエスト中の head 復元または prompt path 再構築の失敗は stdout に `ERR ...` を出して終了コード 1。graph 破棄に失敗した場合も stdout に `ERR --prefill-head-alias: ...` を出す。

## 根拠

- `engine/src/program/generate.cpp:1142-1144` — `--short-read` の既定値 64 とフラグ既定値 false。
- `engine/src/program/generate.cpp:1338-1342` — help にある serve 向け機能説明。
- `engine/src/program/generate.cpp:4117-4118` — parser。short-read を 0 以上に丸め、alias は値なしフラグとして受理。
- `engine/src/program/generate.cpp:8440-8464` — 条件検証、終了コード、MTP bind、head の unload と診断出力。
- `engine/src/program/generate.cpp:12818-12837` — expert-cache slot の借用と prompt chunk 選択。
- `engine/src/program/generate.cpp:13025-13041` — prompt path 初期化へ alias を渡す。
- `engine/src/program/generate.cpp:19164-19231` — head の復元、アドレス変更時の graph 破棄、次リクエスト向け prompt path 再構築。
- `engine/src/program/generate.cpp:21625-21631` — prompt 完了後の slot refill と head 復元。
- `engine/src/prefill/prefill.cpp:2515-2516,2923-2932` — borrowed spill layout の設定と、リクエスト間 relayout の拒否。

調査時の Strata checkout は `main...origin/main` で、未コミット変更はありませんでした。GPU 実行や性能測定は行っていません。性能向上の程度はこの文書では評価していません。
