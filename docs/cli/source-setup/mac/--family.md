# `--family`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS Apple Silicon 向け source setup (`metal/setup_mac.py`) |
| オプション | `--family` |
| 別名 | なし |
| 値 | `qwen`、`unsloth`、`gyro` のいずれか。省略可能 |

## 役割

選択した `--model` のモデル family と指定値が合っているかを確認し、食い違う場合に警告します。family の選択・モデル一覧の絞り込みには使われません。モデルの family は Mac 用モデル表から決まり、オプション指定が合わない場合もモデル表の値が実行に使われます。

## 使い方

ソース checkout のルートで、たとえば次のように実行します。

```sh
./setup.sh --setup --family gyro --model Gyro-S --no-start
```

`setup.py` は macOS で Control mode 以外なら全 argv を `metal/setup_mac.py` に渡します。`setup.sh` などの入口から実行した場合も、この Mac 専用 parser が処理します。根拠: `setup.py:7703-7707`、`setup.py:9068-9069`。

## 値と既定値

- 値は `qwen`、`unsloth`、`gyro` に限定されます。省略時の値は `None` です。parser は不正な値を受理せず、`argparse` の引数エラーとして終了します。根拠: `metal/setup_mac.py:327-331`。
- モデルを省略すると Mac 用モデル一覧から対話的に選びます。`--family` による一覧の絞り込みはありません。モデル一覧は `MAC_MODELS` に基づきます。根拠: `metal/setup_mac.py:392-401`、`strata_control/mac_fit.py:19-34`。
- `--family` の重複指定時の独自処理はありません。通常の `argparse` の store 動作により最後に指定した値が引数値になります。

## 実行時の動作

選択したモデル名から `MAC_MODELS[model].get("family", "qwen")` で family を決定します。`--family` があり、その値がモデルの family と異なるときは `--family <指定値>: <model> is a <family> file; using <family>` の警告を出し、モデル側の family を採用します。たとえば `--family qwen --model Gyro-S` は `gyro` として処理されます。根拠: `metal/setup_mac.py:415-419`、モデル別 family の定義は `strata_control/mac_fit.py:19-34`。

採用された family はダウンロード元・ファイル名・タグ等を定める `setup.py` の `FAMILIES` エントリに使われ、モデル shard の選択にも反映されます。Gyro は単一ファイル、Unsloth はモデルごとの複数 shard、通常の Qwen は標準の Qwen shard 名を使います。pack 処理では family の `pack_args` も渡されます。根拠: `setup.py:572-640`、`metal/setup_mac.py:66-74`、`metal/setup_mac.py:418-420`、`metal/setup_mac.py:509-515`。

既存の Mac 設定が見つかり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていない場合、設定済みモデルをすぐ起動します。この早期分岐の判定には `a.family` が含まれないため、`--family` 単独では設定選択や再セットアップを起こさず、値は実質使われません。根拠: `metal/setup_mac.py:369-371`。

## 適用条件と副作用

この文書は `setup.py` が Apple Silicon の通常 setup を `metal/setup_mac.py` に委譲する `source-setup/mac/` scope の説明です。`setup.py` の一般 parser は macOS 委譲より後に作られるため、同じ `--family` でも受理値と挙動は異なり得ます。根拠: `setup.py:9068-9072`、索引 [`docs/cli/README.md`](../../README.md) の `metal/setup_mac.py` scope 説明。

新規セットアップ経路では `--family` 自体はダウンロードや設定ファイルを書き換えませんが、モデル表を通じて実際に処理する family が決まり、その後のダウンロード、pack、設定・起動スクリプト生成に影響します。これらの処理はモデル選択後に実行されます。根拠: `metal/setup_mac.py:415-420`、`metal/setup_mac.py:428-435`、`metal/setup_mac.py:559-570`。

## 出力とエラー

- 有効な値でもモデル family と食い違うときは警告し、モデルに対応する family で続行します。family の不一致だけを理由に失敗しません。根拠: `metal/setup_mac.py:415-418`。
- 選択肢にない値は parser が拒否します。`parse_known_args` により未知の引数は `not used on a Mac: ...` と警告して続行しますが、これは `--family` に無効値を指定した場合とは異なります。根拠: `metal/setup_mac.py:356-358`。
- family が一致していても、その後の Mac 検査、ダウンロード、build 等が失敗すれば setup は別の理由で停止し得ます。このオプション単独の終了コードは定義されていません。

## 根拠

- parser と unknown argument 処理: `metal/setup_mac.py:327-358`
- 既存設定からの早期起動: `metal/setup_mac.py:369-371`
- モデル選択と family の決定・不一致警告: `metal/setup_mac.py:392-420`
- family ごとの Mac モデル定義: `strata_control/mac_fit.py:19-34`
- family 別ファイル選択・pack 呼び出し: `metal/setup_mac.py:66-74`、`metal/setup_mac.py:509-515`
- family の配布元・タグ等の定義: `setup.py:572-640`
- Mac setup への委譲: `setup.py:7703-7707`、`setup.py:9068-9069`
