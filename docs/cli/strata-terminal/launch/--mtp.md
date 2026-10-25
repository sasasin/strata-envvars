# `--mtp`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--mtp` |
| 別名 | なし |
| 値 | `on` または `off`（値を取る） |

## 役割

モデル起動時に draft layer（MTP）を使うかを指定します。`off` はドラフト層を使わない設定で、`on` はインストール済み設定が無効でも有効にします。parser の説明では、`off` はグラフィックスメモリーと RAM の使用量を減らす代わりに応答を遅くし、小さい GPU や RAM が少ない PC で使う選択肢とされています（`strata_cli/launch/cmd.py:101-103`）。これは Terminal CLI 側の設定です。ネイティブ engine の `--mtp <path|depth>` と同じ値形式ではありません。

## 使い方

```sh
strata launch --model q2_0 --mtp off --no-tui
strata launch --plan --model q2_0 --mtp off
```

1つ目はモデルを起動する指定、2つ目は変更せず起動計画を表示する指定です（`strata_cli/launch/cmd.py:75-82,101-103,138`）。

## 値と既定値

- `on` / `off` の2値を受け付けます。値は前後の空白を除いて小文字化してから検査されるため、大文字・小文字は区別されません（`strata_cli/launch/cmd.py:37-45,101-103`; `strata_cli/launch/settings.py:28`）。
- 省略時は `LaunchSettings.mtp` が `None` です。設定モデル上はインストール済み設定に従い、通常は draft layer を有効にする扱いです。parser の help も既定値を `on` と説明します（`strata_cli/launch/settings.py:77-95`; `strata_cli/launch/cmd.py:101-103`）。
- 値を省略すると argparse の必須値検査で拒否されます。`on` / `off` 以外の値も `_choice` の型変換で拒否され、選べる値を示すエラーになります（`strata_cli/launch/cmd.py:37-45,101-103`）。

## 実行時の動作

`settings_from_args()` は指定値を launch 設定へ格納し、`--preset NAME` と併用した場合は preset の値に上書きします（`strata_cli/launch/cmd.py:197-203,225-235`）。

`off` の場合、launch 用 run config に `"mtp": false` を設定し、`draft_layer.apply()` が engine 引数から MTP 専用の `--mtp`、`--spec-min-p`、`--batch-mtp` を除きます。したがって既存 config に draft layer の引数があっても、launch 時には無効化されます（`strata_cli/launch/runner.py:371-407`; `strata_control/draft_layer.py:25-26,29-56`）。また `modelstate.mtp_choice()` が `off` を返すため、必要ファイルの計画・setup 引数にも反映されます（`strata_cli/launch/modelstate.py:84-88,105-112`; `strata_cli/launch/runner.py:727-745,853-862,1702-1720`）。

`on` の場合、run config の `"mtp"` を true にし、既存の無効設定を上書きします（`strata_cli/launch/runner.py:392-400`; `strata_cli/launch/settings.py:94`）。新規 setup では `qwen`、`swift`、`coder`、`unsloth`、`gyro` の helper family に限り、`--mtp on` を setup 引数に渡します。`off` も同じ family で `--mtp off` として渡され、不要な draft layer の取得を避ける用途があります（`strata_cli/launch/modelstate.py:79-82`; `strata_cli/launch/runner.py:727-745`）。

`--drafting off` を同時に指定すると、`drafting` の選択から MTP 無効が判定され、`--mtp on` より優先して draft layer を無効化します（`strata_cli/launch/modelstate.py:84-88`; `strata_cli/launch/runner.py:392-399`）。`--drafting` はどの drafter を使うかを選ぶ別オプションです。

## 適用条件と副作用

- オプション単独では、非対話・TTY なしの通常起動に必要なモデルや preset の選択には数えられません。`have_choices` の判定に `a.mtp` が含まれず、TTY の対話起動でも選択済み設定を渡す分岐ではなく空の案内画面を開きます。モデル・preset などと併用してください。`--plan` はこの判定を経ず、指定値を含む計画を表示します（`strata_cli/launch/cmd.py:685-710,735-760`）。
- setup で draft layer が不足していれば、`on` は取得対象になり得ます。`off` は取得計画から除外されます。計画上のファイル有無確認と setup 引数の生成は `strata_cli/launch/modelstate.py:105-173`、`strata_cli/launch/runner.py:727-745,1702-1720` にあります。実際の download は通常の launch/setup 処理に伴います。
- `--mtp off` は MTP draft layer を無効にします。launch parser の説明では GPU memory と RAM の節約、応答の低速化が記されています（`strata_cli/launch/cmd.py:101-103`）。MTP 無効時にも残る生成機能など、engine 側の詳細はこの Terminal CLI オプション文書の調査範囲外です。
- このオプションは `--drafting` と独立して保存・適用されます。DFlash2 を含む drafter の選択規則全体は `strata_control/drafting.py` 側の処理であり、ここでは詳細な互換性を断定しません。

## 出力とエラー

値の欠落または不正値は parser の型・必須値検査でエラーになります。設定後の通常起動は、モデルや engine の準備、設定保存、起動を行い、launch runner の失敗は `LaunchError` 経由でメッセージと終了コードを返します（`strata_cli/launch/cmd.py:101-103,784-787`; `strata_cli/launch/runner.py:2011-2048`）。`--plan` は計画内容を表示し「Nothing was changed.」として終了します（`strata_cli/launch/cmd.py:735-760`）。

## 根拠

- parser、選択肢検証、help の説明: `strata_cli/launch/cmd.py:37-45,75-107`。
- preset との合成と値の格納: `strata_cli/launch/cmd.py:197-235`。
- 既定値と設定値の意味: `strata_cli/launch/settings.py:77-95`。
- draft layer の enable/disable と engine 引数への適用: `strata_cli/launch/runner.py:371-407`; `strata_control/draft_layer.py:25-56`。
- setup へ渡す値、適用 family: `strata_cli/launch/modelstate.py:79-88`; `strata_cli/launch/runner.py:727-745`。
- 不足ファイルの判定、計画への反映: `strata_cli/launch/modelstate.py:105-173`; `strata_cli/launch/runner.py:853-862,1702-1720`。
- `--mtp` 単独時の対話・非対話分岐と計画表示: `strata_cli/launch/cmd.py:685-710,735-760`。

調査範囲は指定 commit の Terminal CLI parser、launch 設定、draft layer 制御と setup 計画です。Release 配布物の実行、各 engine backend 上での性能・実機動作は確認していません。
