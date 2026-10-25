# `--mtp`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` からも引数を転送） |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | `on` または `off` |

## 役割

モデル自身の draft layer（MTP）を使うかを選びます。`off` は起動時にMTPを無効にし、`on` は有効にします。これは setup の設定用オプションです。生成されるエンジン引数の `--mtp <path>` とは別で、後者は draft layer の実行ファイル群の場所を示します（`setup.py:9418-9421`）。

## 使い方

Linux のソース checkout で、MTPを使わずにモデルを設定し、設定だけ書いて終了する例です。

```sh
./setup.sh --mtp off --yes --no-start
```

`setup.sh` と `START-HERE.bat` は受け取った引数を `setup.py` に渡します（`setup.sh:17-18, 77`、`START-HERE.bat:30-31, 36-37`）。

## 値と既定値

- 受理値は `on` と `off` のみです。別の値や値なしは、Linux / Windows の `setup.py` parser で argparse の引数エラーになります（`setup.py:8534-8537`）。
- 省略時は `None` です。新規設定では既定でMTPを使い、既存設定の更新では過去の `"mtp": false` を維持します（`setup.py:8534`、`setup.py:6177-6183, 6205-6209`）。
- `on` は `"mtp": true` を明示して、以前保存された `false` を上書きします。`off` は `"mtp": false` を保存します（`setup.py:9677-9685`）。

## 実行時の動作

- `off` でMTP runtime がまだない場合、通常のモデル設定経路では約5.2 GBのMTP取得を見積もりから外し、MTPの取得・変換を行わずに進みます（`setup.py:9238-9247, 9384-9393`）。
- `on`（または省略時の既定）で必要なMTPファイルがなければ、元チェックポイントから約5 GBのテンソルを取得し、`mtp_pack.py` と `mtp_rt.py` でエンジン用データを作ります（`setup.py:9384-9393`）。ダウンロード先は既存のデータ領域内の `mtp` です。
- `off` は既にあるMTPファイルを削除しません。設定生成時に `"mtp": false` を保存し、`draft_layer.apply` が `--mtp`、`--spec-min-p`、`--batch-mtp` をエンジン引数から取り除きます。`--spec` は残るため、MTP draft layer がなくても prompt lookup による推測は残ります（`setup.py:9677-9682`、`strata_control/draft_layer.py:25-56`）。
- 設定更新で `--mtp` を省略しても保存済みの `false` は維持されます。サーバー起動時にも `"mtp": false` を再適用してMTP引数を除外するため、setup が引数を再生成しても有効には戻りません（`setup.py:6177-6183, 6205-6209`、`serve/server.py:3097-3102`）。
- `off` は低RAM経路のVRAM見積もりでもMTP分の余裕を差し引かない設定にします（`setup.py:9143-9149`）。setup は設定を保存し、通常はモデル起動へ進みます。`--no-start` を付けた場合は起動を省略します（`setup.py:9729-9738`）。

## 適用条件と副作用

- `--mtp off` の効果は、MTP draft layer を使うモデルの設定に対するものです。MTPデータが未取得なら取得を省きますが、既存ファイルは残します。既存runtimeの破損が検出された場合は修復分岐が優先され、`off` でも再取得・再生成することがあります（`setup.py:9377-9393`）。
- `--mtp on` はダウンロードや変換を発生させる場合があります。また、以前の `off` 設定を解除し、エンジン設定へMTP runtime のパスを戻します（`setup.py:9384-9393, 9418-9421, 9677-9685`）。
- MTPを使うと約1 GBのGPUメモリと追加RAMを使い、専門家キャッシュに割り当てられるVRAMが減ります。無効化するとその分を節約する代わりに、単語生成速度が低下します（`setup.py:8534-8537, 9680-9685`）。
- macOS は `setup.py` から別の `metal/setup_mac.py` へ処理を渡します。macOS側のparserに `--mtp` はなく、未知引数として `not used on a Mac` の警告が出るだけで、on/offの切替には使われません（`setup.py:8418-8419`、`metal/setup_mac.py:327-358`）。
- Qwen3.6 などエンジン側で `--mtp` が draft 数値を表す構成は、setup option の `on|off` と同じ意味ではありません。ソースには `own_path_config` がその違いを区別する処理があります（`setup.py:6383-6385`）。

## 出力とエラー

- 設定時に `off` / `on` の状態を `[OK]` メッセージで表示します。`off` では使用メモリが減り生成が遅くなる旨も表示されます（`setup.py:9680-9685`）。MTPが未取得で `off` の場合は約5 GBの取得を省く旨を表示します（`setup.py:9384-9385`）。
- Linux / Windows で `on` / `off` 以外を指定すると argparse がusageとエラーを出して終了します。独自の `--mtp` 終了コードは定義されていません（`setup.py:8534-8537`）。macOSでは未知引数警告となり、切替は行われません（`metal/setup_mac.py:356-358`）。
- MTPの取得・変換に失敗した場合の具体的な表示や終了経路は、それぞれの子プロセス処理に従います。この調査では安全な同一revisionのCLI `--help` や実機実行は行っていません。

## 根拠

- parser の値制約と説明: `setup.py:8534-8537`
- 低RAM見積もり、空き容量見積もり、MTPの取得・生成: `setup.py:9143-9149, 9238-9247, 9377-9397`
- エンジン引数へのパス設定とon/offの設定保存: `setup.py:9418-9421, 9677-9685`
- 再設定時の選択維持と既存設定のバックアップ・書き込み: `setup.py:6177-6209, 6312-6340`
- 無効化時に取り除くフラグと、起動時の再適用: `strata_control/draft_layer.py:25-56`、`serve/server.py:3077-3102`
- macOSでの委譲と未知引数の扱い: `setup.py:8418-8419`、`metal/setup_mac.py:327-358`
- 調査対象 revision と状態: commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、調査日 `2026-10-25`。開始時のstatusは `## main...origin/main` で未コミット変更表示なし。
