# `--components-dir`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネントのルートディレクトリ。文字列から `Path` に変換される |

## 役割

導入済み engine の一覧を探す components ルートを指定します。このコマンドは一覧表示専用で、engine の導入・切替・削除は行いません。

## 使い方

```sh
strata components engines --components-dir /srv/strata/components
```

指定するのは `engine/` サブディレクトリそのものではなく、その親のルートです。実装は指定ルート配下の `engine/` を走査します。

## 値と既定値

`argparse` の通常の文字列引数で、parser では `default=None` です。値の存在確認やパス形式の validation は parser 側にありません。実行時は値が truthy なら `Path(value)` を一覧処理に渡します。したがって空文字は指定なしと同じ扱いになり、空でない相対パスも受理されます（相対パスの基準はプロセスの current working directory です）。

省略時は `strata_control.engine_component.components_dir()` の既定値を使います。空でない `STRATA_COMPONENTS_DIR` があればそれが通常の per-user 既定値より優先されます。変数の詳細は [`STRATA_COMPONENTS_DIR`](../../../../envvars/STRATA_COMPONENTS_DIR.md) を参照してください。

ただし、ソース checkout にその checkout 用 `engine-feed/` があり、通常の per-user ルートに engine package が見つからず、かつ `STRATA_COMPONENTS_DIR` が設定されていない場合、`strata components engines` を含むこの CLI の更新系処理は checkout の `engine-feed/` を選びます。`--components-dir` 明示値はこの fallback より先に選ばれます。

## 実行時の動作

`strata_cli/update_cmd.py` の `_common()` がこのオプションを `--feed`、`--backend` などとともに `engines` parser に登録します。コマンド実行時、`run()` は `a.components_dir` を `Path` にして `updater.Context.components` に格納し、そのコンテキストを engine library に渡します。engine library は `<components-dir>/engine/` を走査し、読み取れる engine package と破損 manifest を一覧項目にします。表示するファイル容量の集計も行います。

`--backend` も指定した場合、指定 backend はハードウェア情報へ反映され、一覧中の engine がこの PC で実行可能かを判定する際に使われます。これは一覧の適合表示に関する相互作用であり、`--components-dir` が選ぶ検索ルートは変わりません。`--feed`、`--force`、`--wait`、`--model-config` は共通 parser により受理されますが、`engines` 分岐ではフィード取得・更新処理や wait 処理に進まず、一覧処理には使われません。

## 適用条件と副作用

- 指定したルートが存在しない、またはその配下の `engine/` を列挙できない場合、`scan()` は空の結果を返します。空一覧として表示され、パスの存在を理由とする専用 validation error にはなりません。
- `engine/` 直下の隠しディレクトリは除外し、辞書順で先頭から最大64ディレクトリを読みます。読み取れない manifest は一覧から黙って消すのではなく、読み取り可能な問題情報として項目化します。
- 一覧関数はローカルファイルの読み取りのみを行い、ファイル変更やダウンロードはしません。コマンドは別途稼働中 server 情報を照会しますが、engine の起動・停止・切替は行いません。
- `--output json` または共通 alias の `--json` では一覧を JSON で stdout に出します。通常表示では engine family、version、容量、backend、active/newest/適合状態を出します。

## 出力とエラー

`engines` 分岐は成功時に human 表示または `{"schema_version":1,"ok":true,...}` の JSON を stdout に出し、終了コード `0` を返します。指定ルートや manifest の読み取り不能は `scan()` の空結果または問題項目として扱われます。parser の引数不足・余分な引数など通常の argparse usage error は同 parser の既定処理です。

## 根拠

- `strata_cli/update_cmd.py:47-56,82-83` — 共通 parser における `--components-dir` の文字列値・`None` 既定値と `engines` parser への登録。
- `strata_cli/update_cmd.py:255-270,273-295,312-313` — 明示ルート、既定ルート、source checkout fallback の選択と engine-list 分岐への dispatch。
- `strata_control/engine_component.py:59,176-190,988-1001` — 環境変数名、OS 別既定値、`engine/` の追加、隠しディレクトリ除外・最大64件・列挙失敗時の空結果。
- `strata_control/engine_library.py:91-123,180-195` — 指定ルートの走査、適合判定、一覧データの組み立て、および読み取り専用の説明。
- `strata_cli/update_cmd.py:398-417` — human/JSON 出力と一覧コマンドの終了経路。
- `strata_cli/cli.py:510-518` — `update_parsers` 群への共通 `--json` / `--quiet` 追加。

調査は指定 checkout のソースに限定しました。CLI `--help` や Release 配布物は別途実行・照合していません。
