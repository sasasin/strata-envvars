# `--parallel`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | `N`（整数、1〜8） |

## 役割

モデルが同時に処理するリクエスト数を指定します。モデルが DeepSeek-V4.1-Flash の場合は、指定しなければリクエストを1件ずつ処理し、`2`〜`8` を指定するとその数の会話を同時処理するよう要求します。それ以外のモデルでは、未指定時にグラフィックスメモリーに合わせた値を使います（`strata_cli/launch/cmd.py:100`、`strata_cli/launch/runner.py:1786-1792`）。

## 使い方

```sh
strata launch --model q2_0 --parallel 4
```

DeepSeek-V4.1-Flash で明示的に4会話を同時処理する場合も同じ形式です。

```sh
strata launch --model ist-das-2.00bpw --family deepseek41 --parallel 4
```

## 値と既定値

- `_parallel()` は整数に変換し、`1 <= N <= 8` だけを受理します。整数でない値、範囲外の値は `argparse.ArgumentTypeError` になります（`strata_cli/launch/cmd.py:65-72`）。
- 値を省略した一般モデルでは、利用可能 GPU があれば主 GPU のメモリー量に応じて既定値を選びます。規則は 12 GB 未満で1、20 GB以上で2、24 GB以上で3、32 GB以上で4（境界には0.5 GBの許容幅）です。GPU がない、または情報を取得できない場合は未設定のままです（`strata_cli/launch/settings.py:65-75`、`strata_cli/launch/runner.py:1786-1792`）。
- DeepSeek では未指定時は逐次処理です。GPU に合わせた自動値は設定しません（`strata_cli/launch/runner.py:1786-1792`）。
- `--parallel 1` は逐次処理を指定する値です。サーバー側では `1` 以下に対して並列用 engine 引数を追加しません（`serve/server.py:3594-3602`）。

## 実行時の動作

parser の値は launch 設定の `parallel` に入り、run config の slot/lane 設定と共有 profile の `parallel` override に使われます（`strata_cli/launch/cmd.py:245-246`、`strata_cli/launch/runner.py:1662-1667,1737-1760`）。

- 通常の engine ではサーバーが config の値を `--batch N` として engine に渡します。all-cards split engine が選ばれた場合は split の `--batch` lane 数に反映します（`serve/server.py:3581-3626`、`strata_control/split_engine.py:508-510`）。
- DeepSeek の場合は `--batch` ではなく、DeepSeek engine に `--parallel N` を渡します。値は会話ごとの attention memory を GPU メモリーに確保する同時会話数です。DeepSeek の `--plan` では `N > 1` のとき要求数、実際に扱う会話数、説明行を表示します（`serve/server.py:3603-3619`、`strata_cli/launch/runner.py:2419-2430`）。
- 一般モデルは VRAM の推定収容数を超えても起動を拒否せず、遅くなる可能性を警告します（`strata_cli/launch/settings.py:229-242`）。DeepSeek でも対応環境を外れる条件は警告として扱われ、起動を拒否しません（`strata_cli/launch/cmd.py:461-472`、`strata_control/dsv41_parallel.py:77-117`）。
- `--plan` は起動前の計画表示です。DeepSeek では明示した `N > 1` の動作説明も表示しますが、計画表示後に終了し、画面に「Nothing was changed.」と出します（`strata_cli/launch/runner.py:2419-2430`、`strata_cli/launch/cmd.py:924-954`）。

## 適用条件と副作用

- DeepSeek で選ばれた engine が古く `--parallel` を受け付けないと判定された場合、警告を出し、実行は1件ずつに戻します。要求値は preset に残ります。engine が確認できず対応状態が不明の場合は、通常どおり引数を渡します（`strata_cli/launch/runner.py:1703-1716`、`strata_control/dsv41_flags.py:27-48`）。
- all-cards split engine の config では、明示値が split の lane 数として扱われます。split の適用が失敗または不採用なら、今回追加した `parallel` 値を config から取り除きます（`strata_cli/launch/runner.py:1652-1678`）。
- `--drafting dflash2` など drafting の可否判定にも slot 数が渡されます。CLI の説明では、複数リクエスト時または非対応モデルでは DFlash2 を使わず MTP 単独にするとされています（`strata_cli/launch/runner.py:1552-1565`、`strata_cli/launch/cmd.py:104-107`）。
- 起動時には選択した設定が launch run config と共有 profile に保存されます。次回も使う preset として明示保存する操作は別オプション `--save-preset` です（`strata_cli/launch/runner.py:1625-1627,1737-1760`、索引 [`--save-preset`](--save-preset.md)）。
- 同時処理は1回答あたりの速度や利用可能な GPU メモリーに影響します。DeepSeek のソースにある測定値は Linux 上の特定 GPU での記録であり、他環境の性能保証ではありません（`strata_control/dsv41_parallel.py:19-35,77-117`）。

## 出力とエラー

- 不正な CLI 値は parser で拒否されます。DeepSeek では未対応 engine の場合に「1 request at a time」になる旨の警告を出して続行します（`strata_cli/launch/cmd.py:65-72`、`strata_cli/launch/runner.py:1711-1716`）。
- サーバーは engine に渡せない値や上限超過値を警告し、上限に調整する経路を持ちます。Terminal の parser から指定できる値は既に `1..8` に制限されています（`serve/server.py:3594-3626`）。
- 並列 slot を使う server では slot の save/restore は利用できず、要求は HTTP 501 で拒否されます。また `logprobs` は `max_tokens=1` の要求に限られ、それより長い応答は拒否されます（`serve/server.py:4735-4740,8258-8265`）。

## 根拠

- `strata_cli/launch/cmd.py:65-72,100,245-246,427-472,924-959` — parser、設定反映、モデル別警告、計画と通常起動時の表示。
- `strata_cli/launch/settings.py:65-75,125,229-242` — 設定の未指定値、VRAM による既定値、容量超過警告。
- `strata_cli/launch/runner.py:1552-1565,1617-1627,1652-1678,1703-1760,1786-1792,2419-2430` — drafting、split、DeepSeek engine 対応判定、profile と計画。
- `serve/server.py:3574-3626,4735-4740,8258-8265` — config から engine 引数への変換と server API の制約。
- `strata_control/split_engine.py:508-510`、`strata_control/dsv41_parallel.py:17-35,77-117` — split lane 数、DeepSeek の会話数・説明・環境別警告。

調査範囲はこの checkout のソースです。Release 配布物を別途起動して照合していません。
