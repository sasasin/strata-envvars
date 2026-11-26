# `strata models inspect --install-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect MODEL_ID` |
| オプション | `--install-dir` |
| 別名 | なし |
| 値 | Strata installation の絶対パス（引数は1つ） |

## 役割

`MODEL_ID` の run config を探すインストール先を明示し、inspect の探索範囲をそのディレクトリだけに限定します。省略時は `STRATA_INSTALL_DIR`、または Strata が検出する既知のインストール先を使います。parser は値の型や既定値を別途設定せず、実際のパス検証はモデル検査側で行います（`terminal/strata_cli/cli.py:174-177`; `terminal/strata_control/models.py:69-88,228-244`）。

## 使い方

```sh
strata models inspect qwen_iq3_xxs --install-dir /opt/strata
```

`qwen_iq3_xxs` はセットアップが作成した config 名の ID です。指定先は既存の絶対ディレクトリである必要があります。`--json` を加えると同じ検査結果を JSON で出力できます（`terminal/strata_cli/cli.py:174-177,535-542,635-638`）。

## 値と既定値

- 値は1つのパス文字列です。parser 自体には `type`、`choices`、既定値がないため、値の指定を省略すると `None` になります（`terminal/strata_cli/cli.py:174-177`）。
- 値が指定されると `Path(...).expanduser()` で `~` を展開した後、絶対パスであり、かつディレクトリが実在することを検証します。相対パス、存在しないパス、ディレクトリでないパスは `ProfileError` になります。受理時は `resolve()` 後のパスを使います（`terminal/strata_control/models.py:69-79`）。
- オプションを省略した場合、環境変数 `STRATA_INSTALL_DIR` があればその値が探索先になります。オプションの値がある場合は環境変数より優先されます。環境変数の詳細な仕様は [`STRATA_INSTALL_DIR`](../../../../envvars/STRATA_INSTALL_DIR.md) を参照してください（`terminal/strata_control/models.py:69-79`）。

## 実行時の動作

CLI は `models.inspect(a.model_id, a.install_dir)` を呼び出します。`inspect` はまず `MODEL_ID` の書式を検証し、`all_installs(override)` で探索場所を得て、各場所の `strata-<ID>.json` run config を検索します。明示した install dir または `STRATA_INSTALL_DIR` が使われると探索対象はその1か所です。どちらもなければ Strata の discovery 順で候補を調べ、該当 ID が最初に見つかった場所を採用します（`terminal/strata_cli/cli.py:635-638`; `terminal/strata_control/models.py:69-88,95-107,228-244`）。

選択した config と参照コンポーネントを検査し、結果には config のパス、コンポーネント状態、問題点などを含めます。検査中に config を再読込して内容が変化したことを検出した場合は再試行を促す失敗になります。モデル engine の起動や config の書き換えはこの処理にありません（`terminal/strata_control/models.py:113-136,165-197,228-244`）。

## 適用条件と副作用

- `--install-dir` は `strata models inspect` のスコープです。同じオプション文字列が `models list` や `models move` にもありますが、別コマンドのオプションであり、ここではそれらの意味を扱いません（`terminal/strata_cli/cli.py:168,176,194`）。
- 対象ディレクトリにある config 群を列挙し、ID が一致するものを使います。読み取れないディレクトリや上限を超える config 群は `_paths` のエラーとなり、inspect の探索ループではその候補をスキップします（`terminal/strata_control/models.py:103-109,228-239`）。
- このオプションおよび inspect 経路は探索先の選択と読み取り検査を行います。インストール、ダウンロード、設定ファイルの更新を行う処理は確認できません（`terminal/strata_control/models.py:113-136,180-197,228-244`）。

## 出力とエラー

- 成功時の既定 human 出力はモデル ID、component status、engine 互換性が未検証である旨、config の場所、component 数と issue 数です。JSON 出力では成功 envelope が標準出力に出ます（`terminal/strata_cli/cli.py:535-542,635-638`）。
- install dir が既存の絶対ディレクトリでない場合は `ProfileError` の終了コード5です。ID の形式不正は既定コード2、対象モデルが見つからない場合はコード5です。これらの `ValueError` は人間向けなら `strata: ...` を標準エラーへ、JSON モードなら `ok: false` のエラーオブジェクトを標準出力へ出します（`terminal/strata_control/models.py:73-78,228-241`; `terminal/strata_control/profiles.py:30-35`; `terminal/strata_cli/cli.py:2248-2255`）。
- inspect 中に config が変わった、または無効化した場合は終了コード6で失敗します（`terminal/strata_control/models.py:190-196`）。

## 根拠

- `terminal/strata_cli/cli.py:174-177` — `models inspect` parser、位置引数、`--install-dir` と出力形式の登録。
- `terminal/strata_cli/cli.py:635-638` — parser 値を `models.inspect` に渡し、結果を出力する経路。
- `terminal/strata_control/models.py:69-88` — 明示値と `STRATA_INSTALL_DIR` の優先、絶対既存ディレクトリの検証、明示時の単一 install 探索。
- `terminal/strata_control/models.py:95-109,228-244` — run config の候補形式、ID 検証、探索と不在時エラー。
- `terminal/strata_control/models.py:113-136,180-197` — config の読み取り検証、component 検査、同時変更検知。
- `terminal/strata_cli/cli.py:2248-2255` — `ValueError` の JSON / 標準エラー出力と終了コード処理。
