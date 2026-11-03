# `strata launch --backend`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend 名。GPU メーカー名または内部名（下記「値と既定値」参照） |

## 役割

複数メーカーの GPU がある PC などで、`strata launch` が使う GPU エンジンのメーカーを選びます。これは GPU 番号を選ぶ `--gpu` とは別の指定です。選んだメーカーは、次回以降の起動や engine の更新時にも使う設定として保存されます（`strata_cli/launch/cmd.py:117-119,847-876`、`strata_cli/launch/catalog.py:319-331`）。

## 使い方

```sh
strata launch --backend intel --model q2_0
```

保存済みのメーカー指定を消し、この PC の自動選択に戻す例:

```sh
strata launch --backend auto --model q2_0
```

## 値と既定値

parser は `--backend` の値を必須の文字列として受け取ります。`choices` や型変換は parser に指定されておらず、実行時に前後の空白を除き小文字化して検証します。受理される値は次の通りです（`strata_cli/launch/cmd.py:117-119,847-859`、`strata_control/engine_component.py:474-482`）。

- メーカー名: `nvidia` → `cuda`、`amd` → `hip`、`intel` / `arc` → `sycl`
- 内部名: `cuda`、`hip`、`sycl`
- 自動選択に戻す語: `auto`、`default`、`none`（小文字化されるので大文字も同じ扱い）

値を省略した場合の指定値はありません。help の「default: auto」は選択の既定動作を示す説明であり、オプション省略時に保存済み選択や `STRATA_ENGINE_BACKEND` を消す処理はありません。未指定なら既存の環境変数、保存済み選択、その後に PC の検出結果が使われます（`strata_control/engine_component.py:485-496,514-560`）。

同じオプションを複数回書いた場合は argparse の通常の `store` 動作で最後の値が残ります（`strata_cli/launch/cmd.py:117`）。空文字列は `run_launch` の backend 処理を通らず、指定なしと同様です（`strata_cli/launch/cmd.py:847-848`）。

## 実行時の動作

`auto`、`default`、`none` のいずれかを指定すると、通常起動では保存設定から `engine_backend` を削除し、現在のプロセス環境から `STRATA_ENGINE_BACKEND` も取り除きます。その後は自動判定に進みます（`strata_cli/launch/cmd.py:851-855`、`strata_control/engine_component.py:499-511`）。

メーカー名または内部名を指定すると、対応する内部名を `STRATA_ENGINE_BACKEND` に設定し、このプロセスとそこから起動する処理に適用します。通常起動では同じ選択を Strata の設定ファイルに保存します。保存処理は他の設定キーを維持し、`engine_backend` だけを更新します（`strata_cli/launch/cmd.py:857-867`、`strata_control/engine_component.py:499-511`）。設定ファイルはアプリ用 `STRATA_SETTINGS_FILE` があればそれを使い、そうでなければ Windows では `%APPDATA%/Strata/settings.json`、その他では `$XDG_CONFIG_HOME/strata/settings.json`（未設定時 `~/.config/strata/settings.json`）です（`strata_control/discovery.py:123-131`）。

保存済み選択または環境変数による選択は、インストール済み engine の backend より優先して GPU メーカーを決めます。自動選択へ戻す場合は `--backend auto` などを明示します（`strata_cli/launch/catalog.py:319-331`）。保存済みのメーカーが現在の PC に存在しない場合、保存値は無視され、その PC の検出結果で選び直します（`strata_control/engine_component.py:485-496`）。

`--plan` と併用すると、特定の backend はこのプロセス内の環境変数にだけ設定され、設定ファイルには保存されません。`--backend auto` と `--plan` の併用でも、環境変数は現在のプロセスから外しますが、保存済みの選択は削除しません。plan の最後は「何も変更していない」と出力されます（`strata_cli/launch/cmd.py:851-867,924-953`）。

この処理は `run_launch` の管理系分岐（プリセット一覧・削除、停止、状態表示、API key 表示）の後にあります。さらに backend の保存・環境変更はモデルなどの設定解決や、非対話時に選択を要求するエラー判定より前です。そのため、たとえば `--backend amd` を指定してモデルを指定せず非対話実行し、後で終了コード 2 のエラーになった場合でも、backend 選択が先に保存されることがあります（`strata_cli/launch/cmd.py:799-845,847-891`）。

## 適用条件と副作用

特定 backend 名として認識するのは `cuda` / `hip` / `sycl` 系です。指定が認識されても、その PC や OS に対応 GPU・engine があることまではこの parser の検証で保証されません。後続の hardware/backend 判定と engine 選択に渡され、選択したメーカーに合う GPU がなければ他メーカーの GPU は対象から外れます（`strata_control/engine_component.py:478-482,514-560`、`strata_control/gpu_fit.py:254-269`）。

通常起動ではユーザー設定ファイルを書き換えます。`--plan` はこの永続化を行いません。`--backend` 自体は `LaunchSettings` や保存 preset の設定項目としてコピーされるものではなく、Strata 全体で参照する環境変数・設定値を切り替えます（`strata_cli/launch/cmd.py:212-218,847-876`）。

## 出力とエラー

未対応の値では `strata: '<値>' is not a make of graphics card Strata knows. Use nvidia, amd, intel or auto.` を stderr に出し、終了コード 2 を返します。`--output json` では同じエラーを JSON の `error` として出力します（`strata_cli/launch/cmd.py:790-797,857-859`）。値そのものがない場合は `argparse` が引数不足として拒否します（parser 定義 `strata_cli/launch/cmd.py:117`、トップレベル parse `strata_cli/cli.py:2239-2248`）。

通常起動の選択・解除では、その選択が今後も使われる旨の notice が追加されます。`--plan` の特定 backend 指定では「この plan のみで記憶しない」旨が notice に入り、plan の出力に警告として表示されます（`strata_cli/launch/cmd.py:855-876,924-953`）。

## 根拠

- parser と help: `strata_cli/launch/cmd.py:75-82,117-119`
- backend 値の正規化・設定保存・検出優先順位: `strata_control/engine_component.py:474-511,514-560`
- 起動処理での検証、環境変数設定、`--plan` 分岐: `strata_cli/launch/cmd.py:847-876,924-953`
- 保存設定ファイルの場所: `strata_control/discovery.py:123-131`
- backend と GPU メーカーの選択: `strata_cli/launch/catalog.py:319-331`、`strata_control/gpu_fit.py:254-269`
- 索引上の配置・scope: `docs/cli/README.md:11,1018-1023`（`strata-terminal` の `launch` option として掲載）
