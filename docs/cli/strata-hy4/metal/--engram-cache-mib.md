# `strata-hy4-metal --engram-cache-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--engram-cache-mib` |
| 別名 | なし |
| 値 | 次の引数を1つ消費する。Metal runner では値を検証・解釈しない。 |

## 役割

このオプションは Metal runner では受理されますが、値は Engram キャッシュの設定に使われません。指定すると未使用である旨を stderr に出し、処理を続けます。Engram を有効にした場合もキャッシュ行数は `ENGRAM_DEFAULT_LRU_ROWS` 固定です。

## 使い方

```sh
# 受理はされるが Metal runner では無視され、stderr に警告が出る
strata-hy4-metal --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --engram-cache-mib 256
```

## 値と既定値

parser はこのオプションに続く argv を文字列として消費しますが、数値変換・範囲検証・保存はしません。したがって Metal runner 上で意味のある値や既定値はありません。引数を省略した場合の挙動は parser の `nxt()` が `argv[++i]` を直接読む実装から安全に確認できないため、ここでは記述しません。

## 実行時の動作

Metal runner の引数解析で `--engram-cache-mib` を受けると、次の引数を読み取り、`[args] --engram-cache-mib <値>: not used by the Metal runner` を stderr に出します。その後は通常の引数解析と実行を続けます。この分岐は環境変数やキャッシュ設定を変更しません。

Engram の初期化は `--no-engram` がなく、Engram パスが空でない場合に行われます。その際 `EngramIO::open` には `ENGRAM_DEFAULT_LRU_ROWS` が渡されます。この定数は 6,000,000 行です。従って本オプションを指定してもキャッシュ容量は変わりません。

## 適用条件と副作用

Metal runner 固有の受理分岐です。`--engram` により Engram を使う実行でも、また `--no-engram` により無効化した実行でも、指定値はキャッシュ動作に反映されません。確認できる副作用は stderr の警告だけです。

## 出力とエラー

指定時に stderr へ `[args] --engram-cache-mib <値>: not used by the Metal runner` を出します。この分岐自体は失敗扱いにせず、後続処理へ進みます。モデル読み込みや Engram 初期化など、その後の処理で起こり得るエラーは別経路です。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1508` — `strata-hy4-metal` の引数解析と、値を `argv[++i]` で消費する処理。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608` — オプションを未使用として stderr に通知し、未知引数とは異なり終了せず解析を続ける分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:681-685,1762` — `--no-engram` と Engram パスに応じた初期化、およびキャッシュ行数を固定定数で渡す処理。
- `engine/src/hy4flash/run/hy4_engram.h:21` — `ENGRAM_DEFAULT_LRU_ROWS` の値（6,000,000）。
