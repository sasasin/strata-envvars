# `--install-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--install-dir` |
| 別名 | なし |
| 値 | Strata のインストールディレクトリを示すパス文字列。実行時に `~` を展開し、絶対パスかつ既存ディレクトリであることを検証する |

## 役割

ローカルモデル一覧で探索する Strata インストールディレクトリを明示します。指定時はそのディレクトリだけを調べるため、既定の複数インストール探索に含まれない場所を一覧にするときや、探索先を限定するときに使います。

## 使い方

```sh
strata models list --install-dir /srv/strata/install
```

指定先はモデルの実体ファイルを直接指すのではなく、`strata-<model-id>.json` 形式の run config が置かれるディレクトリです。

## 値と既定値

- parser は値を一つ受け取りますが、型変換や `argparse` 上の必須・パス形式検証は定義していません。実行時に `Path(...).expanduser()` を適用し、絶対パスでない場合またはディレクトリが存在しない場合は `install directory must be an existing absolute directory` として拒否します。シンボリックリンク先が既存ディレクトリであれば `is_dir()` を通り、その後 `resolve()` したパスが使われます。
- 省略時の parser 既定値は `None` です。モデル探索側では `STRATA_INSTALL_DIR` が設定されていればそれを明示指定と同様に扱い、なければ Terminal 自身の設定、ユーザー設定に記録された過去のインストール、Desktop アプリ共有のインストールなどを探索します。最初に run config が見つかった場所が主な場所です。
- 明示値または `STRATA_INSTALL_DIR` が選ばれた場合、探索はその一か所だけです。空のディレクトリも有効な指定先なので、一覧が空でも別のインストール先へフォールバックしません。
- 同じオプションを複数回指定した場合の独自処理はありません。`argparse` が最後に解析した値を Namespace に格納します。

## 実行時の動作

`strata models list` は省略時にローカル run config を列挙します。`--install-dir` があると `models.list_installed()` から `resolve_install()` に渡され、指定ディレクトリだけが一覧対象になります。各ディレクトリでは `strata-` で始まり `.json` で終わるファイル名のうち、共有設定ファイルではなく、モデル ID の形式に合うものを候補として読みます。同じモデル ID が複数の場所にある場合、探索順で先に見つかったものが採用されます（ただし明示指定時は一か所のみです）。

各候補の run config と参照先コンポーネントを読み取り、コンポーネントの有無・状態などを報告します。指定ディレクトリは書き換えず、ファイルのコピー・移動やモデルの起動は行いません。テキスト出力では各モデルの ID、component status、名前（またはエラー）を表示し、該当モデルがなければ探索先と `--install-dir` の案内を表示します。`--output json` を併用すると、結果に `install_dir`、`install_dirs`、`models`、`model_count` などを含む JSON を標準出力へ出します。

## 適用条件と副作用

- `--served` と同時に指定すると、サーバー上の現在のモデル照会にはローカル探索先を適用できないため、終了コード 2 で拒否されます。エラーは通常は標準エラーへ `strata: --install-dir applies only to local installed models` と出力され、`--output json` なら JSON エラーになります。
- `--installed` と `--served` は相互排他です。`--installed` はローカル一覧を明示する parser フラグですが、ローカル一覧が既定の経路であり、実装ではこの値による追加分岐がないため、`--install-dir` の探索範囲や結果は変わりません。
- `--install-dir` は読み取り専用のローカル検査を選択します。各 run config は通常ファイルであること、1 MiB 以下であることなどを確認します。一つのディレクトリに128件を超える対象 config があると、そのディレクトリは正常な列挙を行わず `invalid` として報告されます。コンポーネント検査では engine、tokenizer、モデル引数が参照するファイルやディレクトリの存在を確認します。GPU の live probe やモデル実行はこの一覧経路から要求されません。
- `--url`、`--connection`、`--credential-env`、`--timeout` は `--served` がなければ終了コード 2 で拒否されます。

## 出力とエラー

- 相対パスまたは存在しないパスを指定すると、`ProfileError` がトップレベルで処理され、既定の human 出力では標準エラーにエラーメッセージが出て終了コード 5 になります。`--output json` では `ok: false` とエラー情報を含む JSON が標準出力に出ます。
- ディレクトリ自体が有効でも、読み取り失敗や128件を超える run config がある場合、その場所は一覧中に `component_status: invalid` とエラーを持つ項目として現れる場合があります。個別 run config の JSON 不正、サイズ超過、シンボリックリンク等も、そのモデル項目の状態またはエラーとして報告されます。
- 有効な空ディレクトリでは「インストール先が無効」というエラーにはならず、モデル0件として通常の空一覧メッセージを返します。

## 根拠

- `strata_cli/cli.py:141-152` — `models list` parser、`--install-dir` の値、`--installed` / `--served` の相互排他、出力既定値。
- `strata_cli/cli.py:564-596` — served 経路での `--install-dir` 拒否、connection option の条件、ローカル一覧呼び出しと human/JSON 出力。
- `strata_control/models.py:62-81` — 明示値・`STRATA_INSTALL_DIR` の選択、絶対パス・既存ディレクトリ検証、明示時の単一探索。
- `strata_control/models.py:88-123` — モデル config の対象ファイル名、列挙上限、config 読み取り制約。
- `strata_control/models.py:173-210` — 候補の検査、重複 ID の優先、一覧結果の構造。
- `strata_control/discovery.py:4-14,160-203` — 明示指定時の探索範囲と、省略時のインストール探索順。
- `strata_control/doctor.py:146-220` — run config に基づくコンポーネント存在確認と、live GPU probe が既定で未実行であること。
- `strata_control/profiles.py:30-35`、`strata_cli/cli.py:2119-2173` — `ProfileError` の終了コードと CLI のエラー出力処理。
- `docs/TERMINAL_LAUNCH.md:91-98` — 利用者向け説明との照合。これは補助資料であり、動作の根拠は上記 parser と実装です。

調査範囲は上記 checkout のソースと同一リポジトリ内文書です。既存 CLI の `--help` や Release 配布物は照合していません。
