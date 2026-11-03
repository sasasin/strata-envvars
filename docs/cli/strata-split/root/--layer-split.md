# `--layer-split`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。調査対象 checkout は `main...origin/main` で作業ツリーに変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（`--serve` モード） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | 必須。次の argv 要素を1つ消費するが、値の解釈・検証はしない |

## 役割

このオプションは Strata の通常の layer split 設定との互換のために受理されます。sFNX の `strata-split-N` は全層をカード間で分割して処理する engine であり、この引数の値を保存・参照しません。そのため、指定しても sFNX の分割方式や実行設定は変わりません（`src/split/tools/sfnx.cpp:90`）。

## 使い方

`strata-split-N` を直接起動する場合の形式です。通常は Strata 側が engine を起動します。

```sh
strata-split-2 --serve --native ./model.gguf --mtp ./mtp --layer-split auto
```

`--serve`、`--native`、`--mtp` は起動に必要な引数です（`src/split/tools/sfnx.cpp:81-84,100-101`）。`--layer-split` は単独の真偽値スイッチではなく、直後の値を1つ伴います。

## 値と既定値

値の既定値や許容値の一覧はありません。オプションが現れたとき parser は次の argv 要素を無条件に消費し、解釈せず破棄します。したがって値は `auto`、数値、空文字列などでもこの引数自身による拒否はありません。オプションを省略した場合も、この引数による設定はありません。複数回指定した場合は各回で次の要素を1つずつ消費します（`src/split/tools/sfnx.cpp:75-80,90`）。

値を付けず末尾に置くと `--layer-split needs a value` 例外となり、標準エラーに `sfnx: --layer-split needs a value` を出して終了コード 2 で終了します（`src/split/tools/sfnx.cpp:77-79,1040-1049`）。

## 実行時の動作

parser は `--layer-split` の次の引数を消費するだけで、`Args` や engine の設定には格納しません。Strata の通常の layer split 値を sFNX 側で有効にする動作はありません（`src/split/tools/sfnx.cpp:65-70,90`）。

Terminal の all-cards split 起動経路では、Strata が組み立てる sFNX 引数は `--native`、`--mtp`、`--draft-vocab`、context/spec/lookup/cache/batch と必要に応じた `--vision` であり、`--layer-split` は転送されません。通常 engine 用の `layer_split` 設定は fallback 用設定に保持されます（`strata_control/split_engine.py:250-270`）。なお `strata launch --split-engine` は別オプションです。

## 適用条件と副作用

この引数は `strata-split-N` の引数 parser が処理します。受理されても値の副作用はありません。値を1つ消費するため、その後ろに置く引数が値として吸収される並びでは、後続引数の解釈に影響します。値を欠く場合を除き、このオプション自体の validation failure や警告は確認できません（`src/split/tools/sfnx.cpp:75-98`）。

## 出力とエラー

`--layer-split` の値による stdout/stderr 出力はありません。値不足は上記の parser エラーになります。parser 全体では `--serve` が必要で、`--native` と `--mtp` も必須です。その他の未知引数は `unknown argument <引数>` で拒否されます（`src/split/tools/sfnx.cpp:77-79,98,100-102,1040-1049`）。

## 根拠

- `src/split/tools/sfnx.cpp:72-104` — argv parser、値の消費、必須引数、validation。
- `src/split/tools/sfnx.cpp:1040-1049` — parser 例外の標準エラー出力と終了コード。
- `strata_control/split_engine.py:250-270` — Terminal 側の split engine 引数生成と fallback 設定。
- `docs/cli/README.md:1518-1533` — `strata-split-N` のコマンド scope と当該 option の索引リンク。
