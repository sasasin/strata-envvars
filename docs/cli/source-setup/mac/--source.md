# `--source`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | Apple Silicon 用 `metal/setup_mac.py`（`setup.py` から委譲） |
| オプション | `--source` |
| 別名 | なし |
| 値 | `auto`、`huggingface`、`modelscope` のいずれか（必須） |

## 役割

Apple Silicon の Metal セットアップでモデル関連ファイルを取得するホストを選びます。`auto` は Hugging Face を選ぶ値で、接続不能時に ModelScope へ自動切り替えする意味ではありません。ModelScope を使うには `modelscope` を明示します。

この文書は索引の `source-setup/mac/` scope を対象にします。`setup.py` は macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない場合、通常 parser を作る前に引数を `metal/setup_mac.py` へ渡します。Control install 経路は別 parser/scope です（`setup.py:9068-9069, 9220-9223`）。

## 使い方

Apple Silicon の Strata checkout で、セットアップ時に ModelScope を選ぶ例です。

```sh
./setup.sh --setup --source modelscope
```

直接 Python から呼ぶ場合は `python setup.py --setup --source modelscope` も同じ macOS 委譲経路に入ります。`setup.sh` は引数を `setup.py` に渡します（`setup.sh:6-13`）。

## 値と既定値

- parser は `choices=S.SOURCES`、`default=None` です。共通定義 `S.SOURCES` は `("auto", "modelscope", "huggingface")` です（`metal/setup_mac.py:345-347`; `setup.py:155-156`）。値は小文字の3表記に限られます。値の省略や範囲外の値は `argparse` の引数エラーになり、独自の追加 validation はありません（同上、`metal/setup_mac.py:356`）。
- CLI で指定すると、その値をプロセス内の `STRATA_SOURCE` に設定します。省略時はこの代入をしないため、呼び出し元の環境変数があれば引き継ぎ、なければ downloader の `auto` 相当になります（`metal/setup_mac.py:359-363`; `setup.py:176-184`）。
- downloader は `STRATA_SOURCE` の前後空白を除去して小文字化し、`modelscope` のときだけ ModelScope を選びます。それ以外（`auto`、`huggingface`、空値、その他の環境変数値）は Hugging Face です。環境変数では `ms` も ModelScope として認識されますが、CLI の `choices` では受理されません（`setup.py:176-184`）。

## 実行時の動作

mac セットアップでモデル shard が未取得または完了印がない場合、`metal/setup_mac.py` は `S.download()` を呼びます。共通 downloader は `STRATA_SOURCE=modelscope` の場合、登録済み Hugging Face リポジトリのファイル URL を ModelScope 上の同名ファイルへ対応付けます。ModelScope の URL が応答しなければ警告を出し、Hugging Face endpoint から取得します（`metal/setup_mac.py:451-464`; `setup.py:195-204, 3008-3030`）。ModelScope は固定 revision ではなく現行ファイルを提供する設計で、利用可能なら API が公開するサイズ・SHA-256 を取得後に検証し、hash が公開されない場合は未検証の警告を出します（`setup.py:149-152, 207-218, 3063-3071, 3093-3100`）。

`--source` を指定すると同じ環境変数値は MTP 取得の子プロセスにも渡されます。mac setup は `S.model_source()` の結果を `tools/mtp_fetch.py` に渡してから pack 処理を呼びます（`metal/setup_mac.py:530-536`）。

既に完了印付きの shard は取得をスキップするため、このオプションでそのファイルを取り直しません（`metal/setup_mac.py:455-459`; `setup.py:3008-3014`）。また `--update` 経路はモデルファイルをダウンロードせずに早期終了するので、取得元の指定は実質的に使われません（`metal/setup_mac.py:435-448`）。

## 適用条件と副作用

- 適用先は索引が定める Apple Silicon の `metal/setup_mac.py` 経路です。macOS でも `STRATA_CONTROL_INSTALL=1` の Control install は `setup.py` 側の別経路です（`docs/cli/README.md:13, 1594-1619`; `setup.py:9068-9069, 9220-9223`）。
- ModelScope の URL へ切り替えるのは、downloader が Hugging Face URL から既知リポジトリとファイルパスを特定できた場合です。接続状況に応じて ModelScope から Hugging Face へ fallback することはありますが、`auto` 自体が接続先を自動選択するものではありません（`setup.py:176-204, 3024-3030`）。
- Hugging Face のホストは `HF_ENDPOINT`、ModelScope のホストは `MODELSCOPE_ENDPOINT` で別途変更できます。`--source` はこれらの endpoint 設定を変更しません（`setup.py:111-120, 162-164`）。
- ファイル取得に入ると、選択先へのネットワークアクセスとモデルファイル・完了印などのローカル書き込みが発生します。取得後、mac setup は shard 検査を行い、該当ファイルに個別 SHA-256 pin がある場合はさらに照合します（`setup.py:3008-3023, 3083-3100`; `metal/setup_mac.py:459-464`）。

## 出力とエラー

- 値の欠落・不正値は `argparse` のエラーです。mac parser は `parse_known_args()` を使い、未知の残余引数があれば `not used on a Mac: ...` の警告を出して続行します。これは不正な `--source` 値とは異なり、正規 option として認識された `--source` の choices 違反は parser で拒否されます（`metal/setup_mac.py:345-358`）。
- ModelScope が応答しない場合は `ModelScope does not answer` の警告後に Hugging Face を試します（`setup.py:3024-3030`）。ModelScope の公開 SHA-256 が取得できない場合も警告して完了印を付けますが、そのファイルはその時点では公開 hash による検証を受けません（`setup.py:3093-3100`）。
- 接続が再試行後も失敗する場合、サイズ不足・不一致、固定 hash 検証失敗などは共通 downloader の `fail()` 経路で setup を終了します（`setup.py:904-909, 3035-3068, 3083-3099`）。HF 側の失敗案内は、利用者が `--source modelscope` を明示して再実行するよう示す場合があります（`setup.py:187-192, 3050-3059`）。

## 根拠

- `metal/setup_mac.py:327-363` — mac parser 定義、`--source` の choices/default、未認識引数の警告、環境変数への反映。
- `metal/setup_mac.py:435-464, 530-536` — update 時の早期終了、モデル shard 取得・検査、MTP 子プロセスへの source 伝播。
- `setup.py:149-184, 195-218` — source の選択規則、endpoint、既知 Hugging Face URL の ModelScope 対応付け。
- `setup.py:3008-3100` — 既存ファイルの skip、ModelScope fallback、サイズ/hash 検証と完了印。
- `setup.py:9068-9069, 9220-9223`、`docs/cli/README.md:13, 1594-1619` — mac scope への委譲条件と索引上の範囲。
- `setup.sh:6-13` — shell wrapper から `setup.py` への引数転送。
- [`STRATA_SOURCE` 環境変数文書](../../../envvars/STRATA_SOURCE.md) — 共通 source 環境変数の説明。

調査範囲は上記 commit の checkout 内ソースと索引です。CLI `--help`、Release 配布物、実ネットワークでの取得結果は確認していません。ネットワーク・build・GPU 実行・テストは行っていません。
