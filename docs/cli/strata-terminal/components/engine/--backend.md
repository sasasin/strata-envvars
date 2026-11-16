# `strata components engine --backend`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend 名（文字列）。parser に choices や型変換はない |

## 役割

このPCで使用可能なローカル engine package を調べる際、GPU からの backend 自動判定を指定した backend family で置き換えます。`strata components engine` は状態確認だけを行い、engine のダウンロードやファイル変更はしません。

## 使い方

```sh
# hip family の engine がこのPCで使用可能か調べる
strata components engine --backend hip
```

## 値と既定値

省略時は `None` となり、環境変数・保存済み選択・platform・GPU 検出などに基づく判定を使います。指定値は parser では自由文字列として受理されます。実行時に `split_backend()` で family に正規化され、`amd` は `hip` として扱われます。また `hip-rdna2` など variant 付き backend は family `hip` として扱われます（`strata_control/engine_component.py:1204`）。

## 実行時の動作

CLI は値を `engine_component.status(..., backend=a.backend)` に渡します（`strata_cli/cli.py:2022-2029`）。指定がある場合、status は backend の出所を `requested` とし、backend 検出結果より指定値を優先します（`strata_control/engine_component.py:1200-1217`）。`resolve()` は指定 family に一致し、現在の platform に対応する package を選び、互換性・runtime/driver 条件・署名・ファイル整合性を確認します（同 `:1081-1140`）。

明示した値は `STRATA_ENGINE_BACKEND` や保存済みの backend 選択による自動判定を迂回します。オプション省略時の検出では、まず `STRATA_ENGINE_BACKEND`、次に保存済み選択、macOS platform、GPU adapter や既存の検出ツール等を参照します（同 `:528-574`）。

## 適用条件と副作用

値に parser-level validation はありません。backend family として利用できない値は package に一致せず、通常は engine が利用不可という結果になります。backend family のサポートは platform との組み合わせでも判定されます（`strata_control/engine_component.py:1104-1114`）。`--backend` 自体は読み取り専用で、状態確認処理からダウンロード・展開・変更は行われません（`strata_cli/cli.py:2023-2024,2050`）。

## 出力とエラー

人間向け出力ではPCの platform/backend と判定元、インストール済み package、利用可能な engine または利用不可の理由を表示します。`--output json` と併用すると JSON report を出力します。engine が利用可能なら終了コード `0`、利用不可なら `5` です（`strata_cli/cli.py:2031-2051`）。`ComponentProblem` が発生した場合はエラー出力にして終了コード `2` を返します（同 `:2027-2030`）。

## 根拠

- `strata_cli/cli.py:131-137` — `components engine` parser と `--backend` 登録（`default=None`、選択肢制約なし）。
- `strata_cli/cli.py:2022-2051` — status 呼び出し、出力形式、終了コード、読み取り専用の表示。
- `strata_control/engine_component.py:1200-1228` — status report 作成、指定値の優先、engine 解決。
- `strata_control/engine_component.py:1081-1144` — backend family の選択、platform・互換性・整合性の確認。
- `strata_control/engine_component.py:528-574` — オプション省略時の backend 自動検出。
