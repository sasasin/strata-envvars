# `--parallel`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` からも同じ parser に委譲） |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`。parser 自体には範囲制約がない。通常のエンジン経路では 1 以下は逐次実行にし、2 以上を設定へ保存する |

## 役割

モデルサーバーで同時にデコードするリクエスト数を設定します。省略時は初期値の「1件ずつ」のままですが、setup の標準モデル経路では GPU・モデル・context 等から並列数を提案し、Qwen3.6 経路では条件が合えば対話的に選択肢を示します。提案値を自動適用することはありません（`setup.py:7024-7075`, `setup.py:7598-7609`, `setup.py:9752-9755`）。

## 使い方

Linux/macOS の wrapper、または Windows の `START-HERE.bat` から setup に渡します。たとえば Linux で Qwen3.6 を4枠に設定する例です。

```sh
./setup.sh --family qwen36 --parallel 4
```

直接起動する場合の形は `python setup.py --parallel 4` です。`setup.sh` と `START-HERE.bat` は引数を `setup.py` に渡し、`SETUP.bat` は `START-HERE.bat --setup` に追加引数を転送します（`setup.sh:6-12,76`, `START-HERE.bat:48,52-55`, `SETUP.bat:2-3`）。更新 wrapper も追加引数を委譲します（`update.sh:62`, `UPDATE.bat:79`）。

## 値と既定値

- `setup.py` は `type=int` で解析し、既定値を明示していません。したがって未指定は `None` です。整数でない値や値の欠落は `argparse` の parser error となり、usage とエラーを表示して終了します。setup 側に `choices` や正の範囲検証はありません（`setup.py:8538-8540`, `setup.py:8552-8554`）。同じ引数を複数回指定したときは Python `argparse` の通常の挙動で最後の値が使われます。
- 標準モデル経路と Qwen3.6 経路では、`N >= 2` を `parallel` として設定に保存します。`N <= 1` は `parallel: 1` として保存され、逐次処理になります。負数・0 を含む値も parser では拒否されず、この分岐で1に正規化されます（`setup.py:9688-9696`, `setup.py:7708-7716`）。
- 未指定時、既存 run config に `parallel` があれば setup はそれを引き継ぎます。`parallel` は setup が上書きするキー群 `SETUP_KEYS` に含まれず、`carry_over` が新しい config にないキーを保持するためです。初回設定ではキーを追加せず、サーバーの既定（逐次）になります（`setup.py:6162-6167`, `setup.py:6177-6188`, `setup.py:6312-6328`）。
- `N > 8` も setup の parser と保存処理では拒否・切り詰めされません。サーバーは `--batch N` としてエンジンへ渡します。`--batch-mtp` が有効でない場合はサーバーが最大8枠の案内を出し、エンジン側の調整に委ねます。setup も入力値を維持したまま上限に関する案内を出します（`setup.py:7024`, `setup.py:7066-7074`, `serve/server.py:3132-3153`）。

## 実行時の動作

標準モデル経路では `--parallel N` が指定されると run config の `parallel` に N（または1）を書き込みます。省略時は設定を書き換える分岐を通らず、前項の引継ぎ規則に従います（`setup.py:9686-9696`）。Qwen3.6 の own-path 経路も同様に設定し、未指定かつ対話実行なら GPU 容量等をもとに候補を表示して選択を促します。`--yes` 使用時は質問しません（`setup.py:7598-7609`, `setup.py:7708-7717`）。

起動時、サーバーは設定の `parallel` が1以下なら追加引数を作らず、2以上ならネイティブエンジンへ `--batch N` を追加します。config の `args` にすでに `--batch` または `--slots` がある場合はこの追加を行いません（`serve/server.py:3127-3153`）。エンジンの引数説明は `--batch` / `--slots` の同義性と、通常の実行枠上限2〜8を記しています（`src/program/generate.cpp:910-916`, `src/program/generate.cpp:2610`）。

並列枠は各リクエストの KV cache 等に VRAM を使い、expert cache の余地を減らします。setup は通常経路で GPU VRAM とモデル arena、context、KV 形式等から2〜4枠の推奨値を計算しますが、推奨を強制しません。Qwen3.6 ではモデルサイズ、context、GPU VRAM から別の推奨を計算します（`setup.py:7031-7053`, `setup.py:7485-7509`）。

## 適用条件と副作用

- 索引上の共通 parser は `setup.py` ですが、利用分岐の確認範囲では値を run config に反映する箇所は標準モデル経路と Qwen3.6 own-path 経路です（`setup.py:9686-9696`, `setup.py:7708-7717`）。DeepSeek-V4.1 経路、macOS の `metal/setup_mac.py` 委譲先、SYCL の `sycl/setup_intel.py` 委譲先がこのオプションをどう扱うかは、この文書の範囲では確認できていません。setup の共通 parser が受理することだけをもって各経路で適用されるとは判断できません（`setup.py:7314-7324`, `setup.py:8418-8420`, `setup.py:8561-8564`, `setup.py:8932-8937`）。
- 既存設定を書き換える setup 実行では run config が更新されます。内容が変わる場合は既存ファイルを `.bak` にコピーしてから新しい JSON を書きます（`setup.py:6312-6345`）。
- ここで設定されるのはサーバー内の同時リクエスト数です。`--replicas` のように複数の独立したエンジンを起動する設定とは別です（`setup.py:8541-8544`, `setup.py:9655-9668`）。

## 出力とエラー

- `--parallel 1`、0、負数では「one at a time」の案内を出します（`setup.py:9694-9696`, `setup.py:7714-7716`）。
- 2以上では設定数、各枠のおおよその VRAM 使用量、推奨値との比較を表示します。推奨超過は警告ですが値は保持されます（`setup.py:7066-7074`, `setup.py:7533-7541`）。
- 9以上は設定時点ではエラーになりません。起動時、`--batch-mtp` が有効でなければサーバーが最大8枠の案内を表示し、入力数の `--batch N` をエンジンへ渡します（`serve/server.py:3148-3153`）。エンジンが実際に値を補正する詳細はこの setup オプションの parser ではなく、ネイティブエンジン実装の挙動です。
- 整数に変換できない値は setup の `argparse` が拒否します。setup 本体から呼ぶ parser error の終了コードは標準 `argparse` の2ですが、専用の独自エラー処理はありません（`setup.py:8420`, `setup.py:8538-8540`, `setup.py:8552-8554`）。

## 根拠

- parser 定義と解析位置: `setup.py:8538-8540`, `setup.py:8552-8554`。
- 標準モデル経路での保存・提案出力: `setup.py:7024-7075`, `setup.py:9686-9696`, `setup.py:9752-9755`。
- Qwen3.6 経路での選択・保存: `setup.py:7485-7542`, `setup.py:7598-7609`, `setup.py:7708-7717`。
- 既存設定の引継ぎとファイル更新: `setup.py:6162-6188`, `setup.py:6312-6345`。
- 設定値からエンジン引数への変換: `serve/server.py:3077-3129`, `serve/server.py:3132-3153`。
- エンジン引数の説明と alias: `src/program/generate.cpp:910-916`, `src/program/generate.cpp:2610`。
- wrapper の委譲: `setup.sh:6-12,76`, `START-HERE.bat:48,52-55`, `SETUP.bat:2-3`, `update.sh:62`, `UPDATE.bat:79`。

索引の対象階層と option scope は [`docs/cli/README.md`](../../README.md) の `source-setup` 節に従いました。調査では CLI の `--help` は実行せず、checkout の parser と実装を確認しました。
