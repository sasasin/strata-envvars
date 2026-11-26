# `strata models list --install-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--install-dir` |
| 別名 | なし |
| 値 | Strata のインストール先を指すパス。絶対パスで、実在するディレクトリであること。 |

## 役割

ローカルに保存されたモデル設定の一覧を、指定したインストール先だけから読み取ります。通常のローカル一覧が複数の既知インストール先を探索するのに対し、この指定があると探索先を一か所に限定します。エンジンを起動したり設定を変更したりするオプションではありません。

## 使い方

```sh
# 指定した既存インストール先のモデル設定を JSON で一覧表示
strata models list --installed --install-dir /absolute/Strata/install --output json
```

## 値と既定値

値は `argparse` が文字列として受け取ります。パーサー段階では書式検査をせず、実行時に `~` を展開した後、絶対パスかつ既存ディレクトリであることを検証します。相対パスまたは存在しないパスは `install directory must be an existing absolute directory` で拒否され、終了コードは `5` です。オプションを省略すると `STRATA_INSTALL_DIR` があればその値が使われ、なければ既知のインストール先を探索します。CLI 引数が環境変数より優先されます。明示値が空文字列の場合は Python 側の `override or ...` により環境変数へフォールバックします。

## 実行時の動作

`strata models list` は `--served` が指定されていない場合、値をローカル設定一覧処理へ渡します。明示したインストール先は `resolve_install` が解決・正規化し、`all_installs` はその一か所だけを返します。指定先のトップレベルにある `strata-*.json` のうち、モデル ID として有効でない名前および `*.shared-settings.json` は候補から除外されます。同一モデル ID が通常の複数探索先に重複する場合は先に見つかった場所が採用されますが、明示した場所しか探索しないため、この指定時に別の場所の設定が混ざることはありません。

各候補の設定と参照コンポーネントを読み取り、状態を一覧に含めます。設定ファイルは読み取り専用で開かれ、コンポーネント検査は既定の非 live 検査です。実際のエンジン実行互換性は検証せず `unverified` として報告します。`--served` と併用するとローカル一覧の指定には使えないため、終了コード `2` で拒否されます。

## 適用条件と副作用

このオプションはローカルのインストール済みモデル一覧に適用されます。`--url`、`--connection`、`--credential-env`、`--timeout` は `--served` と併用する接続用オプションであり、`--served` なしに指定するとエラーになります。読み取り処理のため、モデル設定やファイルの移動・変更は行いません。明示したディレクトリ内だけが探索対象となり、別の既知インストール先は追加走査されません。

## 出力とエラー

成功時は既定の human 表示、または `--output json` による JSON を標準出力へ返し、終了コード `0` です。候補がない場合も成功で、human 表示には調査した場所と `--install-dir` の案内が出ます。JSON は `scope: local_run_configs`、解決したインストール先、各モデルの状態、件数などを含みます。

指定先の解決に失敗すると終了コード `5` で、human 表示では `strata: ...` を標準エラーへ、JSON 表示では `ok: false` のエラーオブジェクトを標準出力へ返します。読めないディレクトリや128件を超える候補など、一覧中の探索エラーは一覧全体を直ちに中断せず、該当場所を `invalid` として結果に含めます。個々の設定が無効な場合も、その候補を `invalid` としてエラー内容付きで残します。

## 根拠

- `terminal/strata_cli/cli.py:162-173` — `models list` の parser、`--install-dir` の登録、相互排他の `--installed` / `--served`、出力形式。
- `terminal/strata_cli/cli.py:602-634` — `--served` と `--install-dir` の併用拒否、接続オプションの条件、ローカル一覧への値の受け渡し、成功時出力。
- `terminal/strata_control/models.py:69-88` — 引数・`STRATA_INSTALL_DIR` の優先順位、絶対パス・既存ディレクトリ検証、明示先のみを探索する処理。
- `terminal/strata_control/discovery.py:174-209` — 明示された場所を単独の候補にする分岐と、未指定時の候補探索・順序・重複排除。
- `terminal/strata_control/models.py:95-110, 200-225` — 対象設定ファイルの選別、128件上限、複数場所での先勝ち、一覧結果と探索エラーの表現。
- `terminal/strata_control/models.py:113-136, 180-197` および `terminal/strata_control/doctor.py:297-335` — 設定を読み取り専用で開く処理と、live 検査なしの既定コンポーネント検査。
- `terminal/strata_cli/cli.py:558-573, 2248-2265` — 標準出力・標準エラーの形式と、値検証エラーの終了コード処理。
- 補助資料 `docs/TERMINAL.md:27-39` — `--install-dir` を使った例と、ローカル一覧が既知の場所または明示した場所を調べる説明。現行挙動の根拠は上記ソース。
