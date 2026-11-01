# `STRATA_NO_PRESET`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`serve.server` が Strata engine の設定ファイルを使って起動するとき、保存済み tuning を実行設定に重ねる処理を抑止します。主な設定箇所は `serve/server.py:8588-8615,9074-9078` です。tuning の測定 worker は、測定対象の設定に既存の tuning が重ねられないよう、起動するサーバープロセスへこの変数を `1` にして渡します（`strata_control/tune_session.py:469-483`）。

## 値と判定

| プロセス環境での値 | 判定 | 結果 |
|---|---|---|
| 未設定 | `os.environ.get(...)` が `None`（偽） | 保存済み tuning の overlay を試みる |
| 空文字 `""` | 空文字（偽） | 保存済み tuning の overlay を試みる |
| 空でない任意の文字列 | 真 | `apply_saved_tuning()` が設定を変更せず早期 return する。`"0"`、`"false"`、空白だけの値も抑止値 |

値の数値変換や文字列比較はありません。Python の文字列 truthiness による判定です（`serve/server.py:8593-8594`）。CLI 引数による上書きや別変数との優先順位はなく、サーバープロセス環境の値だけを見ます。設定 JSON の `env` に同名キーを書いても、この判定には使われません。

## 有効になる条件

この判定が呼ばれるのは、`serve.server` が設定ファイルを読み込み、`--engine strata` で起動するときです（`serve/server.py:9074-9078`）。設定ファイルがない起動、または engine が `strata` でない起動では、この箇所からは呼ばれません。

抑止値がなくても、`strata_control.presets.overlay()` が対象の保存先ディレクトリ・active preset を見つけ、選択条件と identity を満たし、設定値の検査を通った場合に限って tuning が適用されます。preset がない、identity の hard mismatch がある、設定値に問題がある場合は適用されず、通常設定が返ります（`strata_control/presets.py:444-488`）。OS、GPU backend、GPU 世代、モデル実行状態による `STRATA_NO_PRESET` 自体の分岐はありません。

## 実行時の詳細

サーバーは設定 JSON を読み、引数表現を正規化した後、engine が `strata` かつ `--config` が指定されている場合に `apply_saved_tuning(cfg)` を呼びます（`serve/server.py:9074-9078`）。環境変数が真なら、この関数は preset モジュールを読み込む前に元の `cfg` を返します。偽なら `strata_control.presets.overlay(cfg)` を実行し、適用可能な tuning の `args`、`env`、`per_request` を設定へ重ねます（`serve/server.py:8593-8612`, `strata_control/presets.py:467-485`）。適用時は `[strata] saved tuning '<名前>' applied: ...`、適用できない理由がある場合は `[strata] saved tuning '<名前>' not applied: ...; re-tune with strata tune auto` 形式の行を出します。抑止時にはこの関数から抑止専用ログは出ません（`serve/server.py:8595-8612`）。

値はこの関数の呼び出しごとに環境から読み、static cache はありません。通常のサーバー起動では設定読込直後の一度だけ評価されるため、起動後にプロセス環境を変更してもその起動時の設定には反映されません（`serve/server.py:9074-9078`）。

Tuning worker は `spawn_env = dict(os.environ)` を作り、追加環境と試行環境の調整後に `spawn_env["STRATA_NO_PRESET"] = "1"` を設定して、`python -m serve.server ... --config ...` を起動します。この代入は継承値や `extra_env` より後なので worker サーバーでは必ず抑止値になります（`strata_control/tune_session.py:469-483`）。worker の起動失敗や ready timeout は通常の `StartFailed` 経路となり、この変数固有の失敗経路はありません（同 `:485-507`）。

engine 用の `child_env()` はサーバープロセス環境をコピーし、設定の `env` をその上に適用してから engine に渡します。そのためプロセス環境の `STRATA_NO_PRESET` は通常子プロセスにも継承され、設定の `env` に同名キーがあれば engine 起動環境ではそちらが上書きします（`serve/server.py:3747-3760,9193`）。調査対象コードでは engine がこの変数を読む処理は確認できず、ここでは一般的な環境引き継ぎとして記述しています。

## 根拠

- 候補一覧上の記載: `docs/envvars/000_envvers.md:1152`。
- 判定、早期 return、preset overlay とログ・例外処理: `serve/server.py:8588-8615`。
- 実際の呼び出し条件と時期: `serve/server.py:9074-9078`。
- tuning worker の環境組み立て、強制設定、起動・失敗経路: `strata_control/tune_session.py:469-507`。
- overlay が設定へ適用する値と、preset がない／不適合の場合の戻り: `strata_control/presets.py:444-488`。
- engine 子プロセス環境への一般的な継承と config `env` の適用: `serve/server.py:3747-3760,9193`。
