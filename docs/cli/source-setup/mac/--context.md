# `--context`（source-setup / Mac）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（Mac 用セットアップ） |
| 入口 | Apple Silicon の macOS で `setup.py` / `setup.sh` を実行すると委譲される |
| parser | `engine/metal/setup_mac.py` |

## 役割

モデルのセットアップ時に、Strata が使うコンテキスト長（トークン数）を指定する。選んだ値は Metal エンジンの実行引数 `--max-context` に設定され、生成される設定ファイルに保存される。

## 使い方

```sh
# Mac 用セットアップでコンテキストを 32768 トークンに指定
./setup.sh --setup --context 32768
```

これはセットアップの例であり、モデルのダウンロードやエンジンのビルドなど、通常のセットアップ処理も実行する。以後の起動だけを行う場合、既存の Mac 設定があれば引数なしの起動経路となり、このオプションを読み直して新しい値を設定する処理には入らない。

## 値と既定値

- 値は Python の `int` で解釈される。未指定時の parser 値は `None`。
- 実際に使う値は `--context` が未指定または `0` なら RAM 容量に基づき決まる。96 GB 未満は `32768`、96 GB 以上は `65536` トークン（`terminal/strata_control/mac_fit.py:254-255`）。
- 正の値に選択肢やセットアップ側の上限チェックはない。既定値より大きく、Mac で測定済みの `32768` を超える値も保持され、その場合は「測定は 32768 まで」と案内する（`engine/metal/setup_mac.py:458-461`、`terminal/strata_control/mac_fit.py:111`）。この表示は値を補正しない。
- 負数もセットアップ側では検証されず、そのまま後述の `--max-context` として渡る。数値に変換できない入力は argparse がエラーとして扱う。

## 実行時の動作

Mac 用 parser は `--context` を `type=int`、既定値なしで登録する（`engine/metal/setup_mac.py:372-403`）。macOS で通常のセットアップを行う際、`ctx = a.context or recommend_context(...)` により値を決定するため、`0` は未指定と同じく RAM 別の推奨値になる（`engine/metal/setup_mac.py:458`）。

決定した `ctx` は Metal 用引数を組み立てる関数へ渡され、`--max-context <ctx>` として設定に入る（`engine/metal/setup_mac.py:596`、`terminal/strata_control/mac_fit.py:264-280`）。設定ファイルは `strata-<model>.json` として書かれ、通常は続けてサーバーを起動する。`--no-start` を併用すれば設定を書いた後に終了する（`engine/metal/setup_mac.py:610-621`）。

## 適用条件と相互作用

- 対象は Mac 用 Metal セットアップである。共通 `terminal/setup.py` は macOS で通常の Metal 経路に入ると `engine/metal/setup_mac.py` に引数を渡す（`terminal/setup.py:9206-9210,11218-11219`）。Control モードや特定の別ファミリー経路はこの分岐の対象外。
- `--context` はモデル、他のセットアップ選択とは独立して `ctx` に反映される。モデルごとのコンテキスト上限をこの parser が検証する処理は確認できない。
- `--context` による測定上限超過の案内は警告相当の情報表示であり、実行継続を止めない。設定が指す実効コンテキストやメモリ需要はモデルとエンジン側にも依存するため、任意の値で動作することをセットアップ側だけから保証できない。

## 出力とエラー

- 引数が整数でない場合、argparse が解析エラーを出し、通常の argparse エラー終了となる（parser 定義: `engine/metal/setup_mac.py:380,403`）。
- `0` は自動推奨値に置き換わる。負数は Mac セットアップでは拒否されず、エンジンの `--max-context` に渡される（`engine/metal/setup_mac.py:458`、`terminal/strata_control/mac_fit.py:280`）。
- エンジンは `--max-context` を読み取り、`0` 以下や `2^31-8` を超える値を不正として終了コード `2` で拒否する（`engine/src/program/generate.cpp:3866,5190-5197`）。したがってセットアップが設定ファイルを書いた後の起動で失敗する場合がある。
- セットアップが最後まで進む場合、コンテキスト値は設定ファイルの `args` に保存される。設定ファイルは一時ファイルを書いてから置き換える方式（`engine/metal/setup_mac.py:610-612`、`terminal/setup.py:7447-7453`）。

## 根拠

- `engine/metal/setup_mac.py:372-403` — Mac 用 parser と整数型の指定、未知引数の警告。
- `engine/metal/setup_mac.py:416-432,458-461` — 既存設定で通常起動する分岐、値の既定化と測定上限の案内。
- `engine/metal/setup_mac.py:596,610-621` — コンテキストをエンジン引数へ渡し、設定保存後に起動または終了する処理。
- `terminal/strata_control/mac_fit.py:111,254-255,264-280` — 測定済み値、RAM 別既定値、`--max-context` への変換。
- `terminal/setup.py:9206-9210,11218-11219` — 共通セットアップから Mac 用実装への委譲条件。
- `engine/src/program/generate.cpp:3866,5190-5197` — エンジン側での引数読取とコンテキスト値の境界検査。
