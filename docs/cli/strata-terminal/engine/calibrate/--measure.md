# `strata engine calibrate --measure`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。

## 概要

`--measure` は `strata engine calibrate` の動作モードを選び、エンジン設定の decode sweep を実行して候補レポートを保存します。設定を適用する操作ではありません。測定結果を適用する場合は、別の `--review-result` / `--apply-result` 手順を使います（`strata_cli/cli.py:176-188, 1065-1075`）。

このフラグは値を取らない `store_true` オプションで、既定値は偽です。同じ parser の必須相互排他グループ内にある `--plan`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のいずれか一つと同時に指定する必要があります（`strata_cli/cli.py:178-186`）。`--profile PROFILE` も必須です（同 `:177`）。

## 使い方

```sh
strata engine calibrate --profile PROFILE --measure --exclusive --out /path/to/new-report.json
```

`PROFILE` は対象の保存済み profile または run-config の参照です。`--exclusive` は測定中に対象デバイスを他のモデルインスタンスが使わないことの確認として必須です。`--out` は新規レポートのパスで、親ディレクトリは事前に存在していなければなりません。存在するファイルやシンボリックリンクは上書きせず失敗します（`strata_cli/cli.py:1065-1072`; `strata_control/calibration.py:289-296`）。

`--measure` に `--exclusive` または `--out` が欠けると終了コード 2 でエラーになります。`--out` は `--measure` 専用であり、`--exclusive` は `--measure`、`--apply-result`、`--rollback-result` に限って有効です（`strata_cli/cli.py:1062-1067`）。

## 実行時の動作と副作用

1. CLI は校正処理を呼び出し、通常の標準出力を標準エラーへ振り替えて測定中メッセージを表示します（`strata_cli/cli.py:1068-1072`）。
2. 対象 profile/run-config を解決し、ロックと排他的 activity lease の下で測定します。対象ポートでサーバーが応答する場合、または管理対象 Strata runtime が起動中の場合は中止します（`strata_control/calibration.py:270-286, 192-229`）。
3. 完全な Strata フォルダー内の `tools/calibrate.py` を使って decode sweep を実行します。Terminal archive にそのツールがなければ、`STRATA_INSTALL_DIR` で `setup.py` と `tools/calibrate.py` のあるフォルダーを指定する必要があります（`strata_control/calibration.py:41-64, 298-313`）。ソース checkout の run-config は測定中も変更しない設計です（同 `:274, 300-302`）。
4. 有効な測定結果から、設定・エンジン・suite・hardware identity などに結び付いた JSON レポートを生成し、新規ファイルとして作成します（同 `:146-166, 314-336`）。適用可能性は測定後に対象 identity を再確認して記録されます（同 `:318-325`）。
5. 成功時は人間向け出力でレポートを確認してから適用するよう案内します。`--output json` を併用すると `ok` とレポート、保存先を含む JSON が標準出力に出ます（`strata_cli/cli.py:189, 1073-1075`; 同 `:535-542`）。

校正対象は現行実装の decode speed 測定です。プレビューが列挙する測定設定は `--pcie-frac`、`--spec-min-p`、`--pool-workers`、`--adapt-every`、`--adapt-swaps`、`--adapt-decay` で、プレビューの所要時間見積もりは約15〜30分です（`strata_control/calibration.py:95-111`）。これは見積もりであり、ここでは実測時間を保証しません。

## 失敗経路と注意点

- 必須の `--exclusive` / `--out` がない場合、引数エラー（終了コード 2）になります（`strata_cli/cli.py:1062-1067`）。
- レポート出力先が既存、親ディレクトリが存在しない、または必須 engine/model component が欠けている場合は測定開始前に拒否されます（`strata_control/calibration.py:147-151, 289-296`）。
- calibration tool が見つからない、エンジンの起動・応答に失敗する、測定がキャンセルされるなどの場合はレポートを作成できず、run-config は変更しないと実装されています（`strata_control/calibration.py:61-64, 303-315`）。
- `--measure` 自体に数値入力や範囲 validation はありません。測定ツールが返す設定値は後段で許可された6設定に限定され、数値・有限性・範囲を検査します（`strata_control/calibration.py:37-38, 169-189, 314-316`）。
- `--measure` は候補の測定とレポート保存までです。設定適用や rollback は別操作です（`strata_cli/cli.py:181-186, 1073-1075`）。

## 根拠と範囲

調査した実装は Terminal CLI parser / dispatcher と `strata_control/calibration.py` です。GPU 上での測定、性能値、OS/backend ごとの実際の所要時間は実行しておらず、確認していません。上記の所要時間はソースにある見積もりを示します。

索引: [`strata engine calibrate` のオプション一覧](../../../README.md)（一覧内の `engine calibrate` 節）。
