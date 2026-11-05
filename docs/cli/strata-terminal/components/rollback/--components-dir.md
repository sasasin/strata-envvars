# `strata components rollback --components-dir`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | コンポーネント格納ルートのパス（文字列） |

## 役割

rollback が参照する engine component と更新状態のルートディレクトリを指定します。指定した場所の `.updates/state.json` に記録された直前の engine を探し、その engine を選択します。`--components-dir` 自体は rollback 対象の版を選ばず、どの component store を調べるかを決めます。

## 使い方

```sh
strata components rollback --components-dir /srv/strata-components
```

rollback 先の store には、前回の更新または切り替えで記録された previous engine が必要です。

## 値と既定値

parser は値を文字列として受け取り、既定値は `None` です。パーサ段階でパスの存在、絶対パスかどうか、ディレクトリかどうかは検証しません。空文字列を渡した場合は Python の条件判定で未指定と同じ既定ルートになります。相対パスは `Path` に変換され、そのまま使われます（呼び出し時の作業ディレクトリ基準です）。同じ option を複数回指定した場合の個別処理はなく、通常の `argparse` の値が `a.components_dir` に渡ります。

## 実行時の動作

- `strata_cli/update_cmd.py` の `_common()` が rollback parser にも `--components-dir` を登録します（`strata_cli/update_cmd.py:47-56,80-82`）。
- 明示値が truthy なら `Path(a.components_dir)` が component root になります。未指定または空文字なら `default_components_dir()` が使われます（`strata_cli/update_cmd.py:255-270,284-285`）。
- 既定選択では `STRATA_COMPONENTS_DIR` があればそのルートを採用します。環境変数がなく、コマンドがソース checkout から実行され、checkout 内 `engine-feed` に engine があり、既定の per-user component directory に engine がない場合は checkout 側 `engine-feed` を使います。それ以外は `engine_component.components_dir()` の per-user 既定ルートです（`strata_cli/update_cmd.py:242-270`; `strata_control/engine_component.py:176-186`）。明示した `--components-dir` はこの既定選択を置き換えます。
- rollback は選ばれた root ごとの `.updates/update.lock` を作成して排他し、同じ root の `.updates/state.json` から `engine.previous` を読みます。該当 engine の manifest と全ファイルを検証し、現在の PC に適合することも確認してから切り替えます（`strata_control/updater.py:136-159,172-211,1355-1377`; `strata_cli/update_cmd.py:286-300`）。
- `--backend` は共通 parser option で、hardware 判定を指定 backend に置き換え、engine 適合性・選択に使われます。`--wait` は稼働中 engine が停止するまで待つ上限秒数です（既定 `0`、つまり待機しません）。`--feed`、`--force`、`--model-config` は共通 parser に存在しますが、rollback 分岐は feed の取得・更新処理へ進まず、これらの値を rollback 処理へ渡しません（`strata_cli/update_cmd.py:48-56,284-300`; `strata_control/updater.py:1355-1377`）。
- rollback はネットワークから engine をダウンロードせず、選択した previous folder を起動時に優先される pin として記録します。状態ファイルは原子的置換で保存され、切替履歴も追記されます。engine が変わる場合、保存済み tuning preset は短い再チェック対象としてマークされる場合がありますが、削除はされません（`strata_control/updater.py:200-211,1303-1352,1355-1357`; `strata_cli/update_cmd.py:304-310`）。

`STRATA_COMPONENTS_DIR` 自体の仕様は [`環境変数文書`](../../../../envvars/STRATA_COMPONENTS_DIR.md) を参照してください。環境変数との優先順位のこのコマンド固有部分は上記の現行ソースに基づきます。

## 適用条件と副作用

- 選択したルートに previous engine の状態記録と component が必要です。別の component directory を指定すると、その directory の状態だけを調べ、他の store の previous engine には切り替えません。
- engine が稼働中の場合、端末対話では待機するか質問し、機械出力または非対話では質問せず、待機指定がなければ busy エラーになります。`--wait SECONDS` を指定すると、その時間まで停止を待ちます（`strata_cli/update_cmd.py:443-459`; `strata_control/updater.py:311-322`）。
- component root 内の lock、状態ファイルを作成または更新します。rollback 自体は download せず、engine package の削除もしません（`strata_control/updater.py:1355-1377,200-211`）。

## 出力とエラー

成功時、通常出力は切替元・切替先と tuning preset の扱いを表示します。`--output json` または `--output jsonl` では成功結果を JSON object で出力します（`strata_cli/update_cmd.py:275-311`）。

- previous engine が記録されていない場合、または既にその engine が選択済みの場合は終了コード `2`。
- previous component が欠落・破損・検証不合格、または現在の PC で使えない場合は終了コード `5`。
- 指定した待機時間内に稼働 engine が停止しない場合は busy error（終了コード `6`）。
- component root の更新 lock を別プロセスが保持している場合は終了コード `7`（`strata_control/updater.py:141-159,1361-1377`）。
- `UpdateError` は通常出力では標準エラーに `strata: ...` と表示され、JSON/JSONL mode では `ok: false` とエラー情報を出します（`strata_cli/update_cmd.py:275-282,347-355`）。

## 根拠

- `strata_cli/update_cmd.py:47-56,80-82` — 共通 parser option と rollback parser への登録。
- `strata_cli/update_cmd.py:242-270,273-311` — component root の決定、rollback 分岐、成功出力。
- `strata_control/engine_component.py:176-190` — 環境変数・OS ごとの per-user root と engine directory。
- `strata_control/updater.py:136-159,172-211` — component root ごとの lock と更新状態ファイル。
- `strata_control/updater.py:1303-1352,1355-1377` — engine 切替、previous の検証、pin と履歴の更新、失敗条件。
- `strata_cli/update_cmd.py:443-459`; `strata_control/updater.py:105-129,286-322` — 稼働確認、待機条件、busy error の終了コード。
