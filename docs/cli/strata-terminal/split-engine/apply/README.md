# `strata split-engine apply`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata split-engine apply` |
| 主な実装 | `strata_cli/split_cmd.py`、`strata_control/split_engine.py` |
| 役割 | run config を調べ、条件を満たす場合に all-cards split engine 用の別 config を生成する |

## 役割

デスクトップアプリが起動直前に作った run config を入力として、通常の layer split から全カードで全レイヤーを処理する split engine へ切り替えるべきかを判定します。適用条件を満たし、`--out` も指定されている場合だけ変換後の run config を出力します。入力は読み込みのみで判定し、モデルや engine のダウンロードも行いません。このコマンドは通常の推論起動ではなく、アプリが構築した設定を起動用に変換する操作です（`strata_cli/split_cmd.py:1-5,25-53`）。

Terminal の `strata launch` も起動時に同じ `strata_control.split_engine` の判定を呼びます（`strata_cli/launch/runner.py:1696-1729`）。split engine の構成・適用条件については [Strata checkout の all-cards split engine 説明](../../../../../../../Niko1221/Strata/docs/SPLIT_ENGINE.md)を参照してください。

## 使い方

```sh
# 判定結果だけを表示し、別 config は作らない
strata split-engine apply --config /path/to/run-config.json

# 判定が適用可の場合に、split 用 config を指定先へ書く
strata split-engine apply --config /path/to/run-config.json --out /path/to/split-run-config.json

# 同じ結果を機械処理向け JSON で受け取る
strata split-engine apply --config /path/to/run-config.json --output json
```

`--config` は必須です。`--out` は任意で、省略時は判定のみ行い、適用可能でもファイルは作りません。各引数の詳細は [`docs/cli/README.md`](../../../README.md) の `strata split-engine apply` 節にあるオプション文書を参照してください。

## 判定と実行モード

このコマンド自体に `auto` / `on` / `off` の引数はありません。環境変数 `STRATA_SPLIT_ENGINE` が設定されていればそれを優先し、空または未設定なら入力 config の `split_engine` を読みます。`on` / `1` / `true` / `yes` は要求、`off` / `0` / `false` / `no` は無効として扱い、それ以外の値は `auto` になります。既定も `auto` です（`strata_control/split_engine.py:395-408`）。

split engine を適用するには、実装上、Linux、同一メーカー・同一型/メモリー容量の 2〜4 枚の対応 GPU、対応する Qwen3.8-Flash-Next のモデル形状とテンソル型、全 routed expert を載せる GPU メモリーと十分な空き RAM、131072 以下の context などが必要です。engine package 内にカード数・構成に合う `strata-split-*` 実行ファイルがあること、draft layer または明示選択された DFlash2 pack、`draft_vocab_en.bin` が見つかることも判定に含まれます。自動適用はさらに GPU 世代・カード数・AMD の expert 型に関する gate を通ります。未対応条件では通常の layer split 用 config を維持し、理由を返します（`strata_control/split_engine.py:189-261,416-429,476-565`）。

run config に engine 独自引数 (`user_args`) または replicas がある場合、drafting が `off` の場合、あるいは `--kv` が `int8` 以外の場合も適用されません。DFlash2 を名前指定した構成は通常 `auto` では適用されず、`on` の明示が必要です（`strata_control/split_engine.py:502-517`）。明示的に `on` にしてもルール全体を迂回するわけではありません。未テスト条件を許容する環境変数 `STRATA_SPLIT_ALLOW_UNTESTED=1` はこのコマンドから判定関数へ渡されます（`strata_cli/split_cmd.py:41-43`）。

## 主な動作と副作用

- 入力は UTF-8-SIG として JSON 読み込みされ、JSON object 以外は不正入力です。判定は JSON の複製に対して行われます（`strata_cli/split_cmd.py:35-43`）。通常は入力ファイルを変更しませんが、`--out` に `--config` と同じパスを渡すと置換対象になるため、別のパスを指定してください。
- 適用可の場合は既存 config の一般設定を引き継ぎつつ、実行ファイル・引数・環境変数を split engine 用に組み立てます。元の engine 設定は `split_fallback` に退避され、split engine が起動できない場合の fallback 情報になります。`--out` を指定したときは出力先の隣に `.tmp` を作成してから `os.replace` で出力先へ置き換えます（`strata_control/split_engine.py:264-288`、`strata_cli/split_cmd.py:45-53`）。
- 新規の一時出力ファイルは mode `0600` を指定して作成します。出力先の親ディレクトリは作成しません。既存の出力先は `os.replace` によって置き換えられます。したがって、入力や既存ファイルを保持したい場合はそれらとは別の出力パスを指定してください（`strata_cli/split_cmd.py:46-52`）。
- 適用判定は拒否や処理例外でコマンドを失敗させず、split 不使用の理由を返します。auto での条件不一致は `strata_control` 側では quiet 扱いですが、この明示的な CLI は返却行、または既定の `Using the normal layer split.` を表示します（`strata_control/split_engine.py:631-656`、`strata_cli/split_cmd.py:54-59`）。

## 出力とエラー

既定の human 出力は判定行を標準出力へ表示し、終了コード `0` です。`--output json` は `schema_version: 1`、`ok`、`split`、`line`、`warn`、`reasons`、`cards`、`written` を含む JSON を標準出力へ出します。判定不可は `ok: true` のまま `split: false` と理由を返す結果であり、コマンド失敗ではありません（`strata_cli/split_cmd.py:25-33,54-59`）。

入力ファイルを開けない、JSON を解析できない、またはトップレベルが object でない場合は human では標準エラーに `strata:` 付きのメッセージ、JSON では `ok: false` と `split_engine_failed` を出し、終了コード `5` を返します（`strata_cli/split_cmd.py:28-40`）。引数不足・未知の引数など argparse の構文エラーはコマンド処理前に発生します。出力先の書き込みに失敗した場合は共通 CLI の `OSError` 処理に入り、終了コード `6` になります（`strata_cli/cli.py:2250-2259,2188-2195,529-534`）。

## 根拠

- `strata_cli/cli.py:172-175,2156-2158` — parser 登録と `split-engine` の実行委譲。
- `strata_cli/split_cmd.py:16-23` — `apply` の parser、必須入力、任意出力、出力形式。
- `strata_cli/split_cmd.py:25-59` — 入力検査、判定呼び出し、ファイル生成、標準出力と個別エラー。
- `strata_control/split_engine.py:395-408,476-565,631-656` — mode 優先順位、適用条件、config 変換、例外時の扱い。
- `strata_control/split_engine.py:189-261` — platform、GPU、モデル、context、メモリーの一般判定。
- `strata_cli/launch/runner.py:1696-1736` — Terminal launch からの同じ判定利用。
- Strata `docs/SPLIT_ENGINE.md:26-58` — 利用者向けの適用条件と fallback の説明。実装上の挙動の根拠は上記ソース。
