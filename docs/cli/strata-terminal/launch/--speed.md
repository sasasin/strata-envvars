# `--speed`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。調査開始時の作業ツリーは `main...origin/main` で未コミット変更なし。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--speed` |
| 別名 | なし |
| 値 | `faster` または `full` |

## 役割

DeepSeek-V4.1-Flash の1語あたりに使う expert 数を選びます。`faster` は6個中5個を使い、`full` は6個すべてを使います。`faster` では品質がわずかに変わる可能性があると CLI は説明していますが、性能差の測定結果はこの文書では確認していません（`strata_cli/launch/cmd.py:108-110`、`strata_cli/launch/settings.py:31-33`）。

## 使い方

```sh
strata launch --family deepseek41 --model ist-das-2.00bpw --speed faster --no-tui
strata launch --preset "DeepSeek" --speed full --no-tui
```

モデル識別子はカタログにある名前を使います。`--model` はモデル一覧から解決され、指定した preset に `--speed` を重ねた場合は今回の起動設定に反映されます（`strata_cli/launch/cmd.py:201-220, 244-245`）。

## 値と既定値

- 値は必須で、受理値は `faster` と `full` です。parser は値の前後空白を除き、小文字化してから照合します。そのため大文字・混在ケースも受理されます（`strata_cli/launch/cmd.py:37-45, 108`、`strata_cli/launch/settings.py:31`）。
- それ以外の値や空文字列は argparse の型変換エラーになります。選択肢と、近い候補があれば候補名を含むエラーを出します。parser は `--speed` を `store` action で登録しており、同一オプションを複数回渡すケースでは通常の argparse の動作として最後の値が使われます（`strata_cli/launch/cmd.py:37-45, 108`）。
- 未指定時は設定値を持たず、対応エンジン自身の `--experts auto` に任せます。Strata の計画表示上の既定は、使用 GPU が統合 GPU の場合、または使用カードの VRAM 合計が16 GiB以下の場合に `faster`、それ以外は `full` です（`strata_cli/launch/settings.py:36-41, 111`、`strata_cli/launch/runner.py:428-459, 2011-2022`）。

## 実行時の動作

CLI は指定値を launch settings に格納します。起動時に選ばれた engine が確定した後、DeepSeek の engine が `0.1.50` 以上なら、`faster` を `--experts 5`、`full` を `--experts 6` として実行設定の `args` に加えます。既存の `--experts` または `--experts=...` は取り除いて置き換えます（`strata_cli/launch/cmd.py:240-245`、`strata_cli/launch/runner.py:401-425, 475-490, 1390-1396, 2034-2039`）。

`--full-quality` は `--speed full` と同じ指定です。両方を渡した場合は `--full-quality` が優先されます。`--full-quality` と `--speed faster` の組み合わせでは警告を記録して `full` にします（`strata_cli/launch/cmd.py:108-111, 240-245`）。

## 適用条件と副作用

- 別のモデル family では `--speed` と `--full-quality` を使わず、全 expert を使う旨の警告を出して設定値を外します（`strata_cli/launch/cmd.py:343-353`）。
- DeepSeek 用の engine が見つからない、または version を特定できない場合、あるいは `0.1.50` より古い場合、明示値から `--experts` は渡されません。version が不明・古いこと自体はこの処理ではエラーにせず、speed 表示も省略します（`strata_cli/launch/runner.py:401-425, 2024-2039`）。
- 対象モデルでは DeepSeek 専用 engine package を使い、Strata engine は使いません（`strata_cli/launch/runner.py:682-687, 1424-1429`）。実際の起動では、選択値が engine の起動設定に反映されます。`--plan` は設定を変えずに終了するモードで、対応 engine があれば speed の計画表示を含みます（`strata_cli/launch/cmd.py:755-784`、`strata_cli/launch/runner.py:2004-2022`）。
- 起動後のサマリーでは、engine のログに `experts per word: N` があればその実測起動値を表示に使います。ログが読めない場合や値がない場合は、ログ値による補正を行いません（`strata_cli/launch/runner.py:462-472, 2041-2050`、`strata_cli/launch/cmd.py:842-849`）。

## 出力とエラー

不正な値は argparse が usage と引数エラーを表示します。別モデルでの指定、または `--full-quality` との競合は拒否ではなく警告です。CLI の通常の実行失敗は `strata: ...` を stderr に出して終了コードを返し、`--output json` ではエラー JSON を stdout に出します。これらの一般エラー出力経路は `strata_cli/launch/cmd.py:652-663, 867-872` にあります。speed 固有の終了コードは定義されていません。

## 根拠

- `strata_cli/launch/cmd.py:37-45, 108-111` — 値の正規化・検証と parser 定義。
- `strata_cli/launch/cmd.py:240-245, 343-353` — 設定への反映、`--full-quality` 優先、対象外モデルでの警告と無効化。
- `strata_cli/launch/settings.py:31-48, 111` — 受理値、未指定値、既定表示の補助規則。
- `strata_cli/launch/runner.py:401-425, 428-459, 475-490, 1390-1396` — engine version 条件、既定計算、engine 引数への変換と起動設定への適用。
- `strata_cli/launch/runner.py:2011-2050`、`strata_cli/launch/cmd.py:755-784, 842-849` — 計画・起動結果の表示。
