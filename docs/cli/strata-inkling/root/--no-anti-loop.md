# `--no-anti-loop`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--no-anti-loop` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--serve` のリクエスト生成時に、生成トークンの反復パターンを検出してリクエストを早期終了する処理を無効にする。既定では反復検出が有効で、フラグを指定すると無効になる。

## 使い方

```sh
strata-inkling --serve --native model.strata --no-anti-loop
```

この例では標準入出力の serve モードでモデルを使い、反復検出による早期終了を止める。`--serve` のモデル指定を含む起動形式は parser のヘルプ文字列に記載されている（`engine/src/inkling2/ink_main.cpp:496`）。

## 値と既定値

- 値を取らない。parser はこの引数を認識すると `cfg.anti_loop = false` にする（`engine/src/inkling2/ink_main.cpp:486-487`）。
- 既定値は `true`（反復検出を有効）である（`engine/src/inkling2/ink_serve.h:431-438`）。
- 同じフラグを複数回指定しても、同じ `false` を再設定するだけで、追加の効果はない。
- 専用の値検証や失敗経路はない。未知のオプションは `unknown option` を stderr に出し、終了コード `2` で終了する（`engine/src/inkling2/ink_main.cpp:499-501`）。

## 実行時の動作

serve ループは各リクエストの生成トークン列に反復検出を適用し、検出された場合は終了理由 `stop` でリクエストを完了させる。通常生成経路に加え、speculative/draft 生成の経路にも同じ条件判定がある。フラグを指定するとそれらの `cfg.anti_loop` 条件が偽になり、この検出による完了だけが起きなくなる（`engine/src/inkling2/ink_serve.h:798`, `860`, `994-1010`）。

検出器は生成トークンが96個未満なら不一致とし、それ以上では周期1〜32の反復を調べる。周期1〜4では24反復分、それより長い周期では10反復分の一致を条件にする（`engine/src/inkling2/ink_serve.h:225-242`）。

このフラグは parser 上どのモードでも受理されるが、設定値を参照するのは serve ループだけである。したがって `--serve` を付けない直接生成では効果がなく、直接生成のループは EOS/EOT または生成数で止まる（`engine/src/inkling2/ink_main.cpp:486-487`, `571-613`）。bench、info、selfcheck なども `anti_loop` を参照しない（モード分岐: `engine/src/inkling2/ink_main.cpp:544-573`）。

反復検出を無効にしても、EOS/EOT、生成上限、hold 条件、コンテキスト上限などによる終了は別条件として残る（`engine/src/inkling2/ink_serve.h:994-1010`）。検出に伴う装置・ファイル操作はなく、serve の完了通知は通常と同じプロトコル経路で出力される。solo/外部リクエストでは `DONE`、admitted な slot リクエストでは `BDONE` が出力される（`engine/src/inkling2/ink_serve.h:496-520`）。

## 適用条件と副作用

- `--serve` のみで効果がある。値は起動時の引数解析で設定され、実行中に変更する経路は確認できない。
- フラグ自体によるネットワーク待受、ファイル変更、追加のプロセス起動はない。serve の通信は `ServeInput` 経由の標準入出力である（`engine/src/inkling2/ink_serve.h:487-490`）。
- `--help` のソース内表示には `--no-anti-loop` の記載がない一方、parser は受理する（`engine/src/inkling2/ink_main.cpp:486-497`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-384, 486-501` — 引数処理、値なしフラグ、未知オプションの失敗経路、help 表示。
- `engine/src/inkling2/ink_main.cpp:540-573, 575-613` — mode dispatch と、serve 以外の直接生成経路。
- `engine/src/inkling2/ink_serve.h:225-242, 431-438` — 反復検出の閾値・条件と設定の既定値。
- `engine/src/inkling2/ink_serve.h:798, 860, 994-1010` — 通常・speculative 生成経路での判定と他の終了条件。
- `engine/src/inkling2/ink_serve.h:496-520` — リクエスト完了理由とプロトコル出力。
