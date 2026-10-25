# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime status` |
| オプション | `--json` |
| 別名 | なし。`--output json` でも同じ出力形式を選べる |
| 値 | 値を取らない真偽フラグ |

## 役割

status の結果を機械可読な JSON で stdout に出します。profile の状態を調べる処理自体は `--json` の有無で変わりません。

## 使い方

```sh
strata runtime status --profile my-profile --json
```

`--profile` は必須です。JSON を選ぶ別の書き方は `strata runtime status --profile my-profile --output json` です。

## 値と既定値

`--json` は値を受け取りません。省略時は `--output` の既定値 `human` が使われ、明示すると `--output json` に切り替わります。`--output` は `human` または `json` のみを受け付けます。明示的に `--output human` と `--json` を併記すると、CLI の正規化処理が `--json` を優先して JSON にします。短縮別名はありません。

## 実行時の動作

parser は `runtime status` 専用に `--profile` と `--output` を宣言し、共通 one-shot オプションの登録処理で `--json` を追加します。トップレベルの引数処理でこのフラグが立っていると `output` が `json` に設定され、runtime dispatcher が `management.runtime_action("status", profile, ...)` を呼びます（`strata_cli/cli.py:213-215,508-515,2232-2237,1331-1356`）。

management 層は status を plan なしで実行し、`strata_control.runtime.status(profile)` の結果を返します（`strata_control/management.py:231-234`）。runtime 状態ファイルがなければ `state: "stopped"`、所有 host が失われた古い状態なら `state: "stale"` と `owner_host_lost` を返します。host の lease が有効な場合はローカル制御経路で `status` を問い合わせます（`strata_control/runtime.py:444-455`）。

成功結果は `schema_version: 1` と `ok: true` を含む JSON オブジェクトとして stdout に出力され、runtime status の返却値が同じオブジェクトのトップレベルに展開されます。stopped と stale の具体的な項目は上記のとおりですが、稼働中 host が返す status の全フィールドはこの CLI 側で固定していません（`strata_cli/cli.py:1359-1360`）。

## 適用条件と副作用

`--json` は status の実行経路、照会対象、状態判定を変えず、出力形式だけを選びます。指定する profile 名は `PROFILE_ID` が受理する形式である必要があります。この status 経路は profile 設定を読み込まず、runtime state を profile 名で照会します（`strata_control/runtime.py:95-98,444-455`）。

status は profile の runtime state を読むときに runtime directory を解決します。`STRATA_RUNTIME_DIR` が設定されていればその値を展開して使い、未設定なら既定の state directory 配下の `runtime` を使います。ディレクトリがまだなければ作成されます。また override は絶対パスでなければ拒否されます（`strata_control/runtime.py:101-111`）。profile が稼働中の場合は所有 host のローカル制御 endpoint に照会します。POSIX では private Unix socket、Windows では loopback 接続を使う実装です（`strata_control/runtime.py:402-415`）。

## 出力とエラー

- status の結果が `ok: false`（例: stale）なら、その結果も JSON で stdout に出し、CLI は返却値の `exit_code`（stale では `6`）を終了コードにします（`strata_control/runtime.py:452-455`, `strata_cli/cli.py:1359-1373`）。
- state file が不正・非公開・読めない場合、runtime control に接続できない場合、応答が不正または過大な場合などは `ProfileError` 等が発生します。`--json` が有効なら CLI の共通エラー処理は `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` を stdout に出します。例として、接続不能は code `3`、応答不正・過大は code `6` です（`strata_control/runtime.py:215-235,402-440`, `strata_cli/cli.py:527-532,2166-2188`）。
- `--profile` の欠落、`--output` の無効値など argparse の構文エラーは JSON 化されず、usage とエラーを stderr に出して終了コード `2` になります。これらは parser 段階で `--json` の出力正規化より先に拒否されます（`strata_cli/cli.py:213-215,2223-2235`）。

## 根拠

- `strata_cli/cli.py:202-215` — `runtime status` parser と `--profile` / `--output` の定義。
- `strata_cli/cli.py:508-515` — status parser を含む one-shot parser への `--json` 追加。
- `strata_cli/cli.py:2223-2237,1331-1373` — `--json` の `output=json` への変換、status 実行、JSON 出力、終了コード。
- `strata_control/management.py:231-234` — status action の委譲。
- `strata_control/runtime.py:95-111,215-235,285-295,402-455` — profile/runtime directory の検証、状態読み込み、owner lease と制御照会、status の結果と失敗経路。

調査範囲は上記 revision の checkout 内の parser と Python 実装です。同一 revision の CLI help、Release 配布物、各 OS での実行結果はこの調査では確認していません。
