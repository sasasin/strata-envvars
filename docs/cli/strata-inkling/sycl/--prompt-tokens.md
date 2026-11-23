# `--prompt-tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL） |
| オプション | `--prompt-tokens` |
| 別名 | `--prompt-ids` |
| 値 | カンマ区切りの整数列。値を1引数で指定する |

## 役割

SYCL 版 Inkling-2 の検証・計測経路で使う入力 token ID 列を指定する。通常の対話生成用 prompt ではなく、selfcheck、speculative decode の parity check、benchmark、parallel sweep が処理する token 列である。これらの処理を指定しない場合、この値だけで生成処理は起動しない。

## 使い方

```sh
# token ID 101, 102, 103 を使って計測する
strata-inkling-sycl --model ./model.strata --bench --prompt-tokens 101,102,103

# 同じ入力で通常 decode と D-Spark decode の一致を確認する
strata-inkling-sycl --model ./model.strata --spec-check --prompt-ids 101,102,103
```

`--model` には Inkling-2 の `.strata` モデルを指定する。計測・検証モードは同時に複数指定でき、指定された各処理が同じ prompt 列を使う。

## 値と既定値

- 起動時の既定値は `1,2,3,4,5,6,7,8`。
- 値はカンマで分割され、空でない各要素を `std::atoi` で `int` に変換する。厳密な整数形式の検査や変換失敗の報告はない。たとえば空要素は無視され、数字で始まらない要素は `atoi` の結果 `0` になる。また、数字の後ろに余分な文字があっても先頭の数値部分が変換される。
- 値全体が空、または区切りだけで分割結果が空になる場合は、後段で既定列 `1,2,3,4,5,6,7,8` に置き換わる。
- 同じオプションまたは alias を複数回指定した場合、引数走査中に `prompt_csv` が更新され、最後の値が使われる。
- 後続 argv がない場合、parser の `need()` は空文字列を返すため、結果的に既定列へ戻る。次の引数が別のオプション表記でも値として消費し、そのオプションは後続 parser に渡らない。

## 実行時の動作

parser は `--prompt-tokens` と `--prompt-ids` を同じ分岐で受理し、文字列を保存する。モデルと runner の初期化後に CSV を整数列へ変換し、空列なら既定列を復元する。その列は selfcheck で slot 0 の prefill 入力となり、spec-check と benchmark では greedy decode の prompt として渡される。parallel sweep では各 slot の初期 token を列から順に繰り返して埋める。

このオプション自体は結果を出力しない。実行する処理は他のモード指定に依存する。`--info` の経路はモデル情報を表示して早期 return するため、prompt 列の変換・利用には進まない。

## 適用条件と副作用

- `--model` がない場合は usage を標準エラーへ出して終了コード `1` で終了する。usage の表示には `--prompt-tokens` が列挙されていない。
- token ID の非負性・語彙範囲を検証する処理は parser と prompt 組み立て箇所にない。値は runner から embedding lookup kernel へ渡され、kernel は token ID を embedding 配列の添字に使う。範囲外値の安全性や結果はソースから確定できないため、有効なモデル語彙内の ID を指定する必要がある。
- モードを実行するとモデルをロードし、GPU/SYCL runner を初期化して計算する。`--prompt-tokens` を指定しただけではモデルロードを省略しない。
- `--info` はモデルを probe した後に終了するため、このオプションの値は使用されない。

## 出力とエラー

出力形式は併用するモードによる。selfcheck は prompt を使って forward pass を行い `[SELFCHECK]` 行を表示する。spec-check は通常 decode と speculative decode の token を比較し、一致しなければ token 列を追加表示して終了コード `3` を返す。benchmark は prompt 長・prefill/decode の計測結果を `[BENCH]` 行に出力する。parallel sweep は各 concurrency の集計を `[PAR-SWEEP]` 行に出力する。

prompt CSV の形式エラー専用メッセージや終了コードは実装されていない。`atoi` による変換と空列時の既定値への置換が行われる。kernel 実行の成否が prompt によってどう報告されるかは一律ではなく、selfcheck・spec-check・benchmark の呼び出し側では `forward_batch` / `run_greedy_decode` の戻り値を検査しない箇所がある。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:19-29` — CSV 分割、空要素のスキップ、`atoi` による変換。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:103-114` — 既定列と値引数取得関数。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:144` — `--prompt-tokens` と `--prompt-ids` の parser 登録。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-169` — model 未指定時の usage と終了コード。表示 usage にこのオプションは含まれない。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:173-181` — `--info` の probe-only 早期終了。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:198-207` — runner 初期化後の値変換と空列時の既定値。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:209-223` — selfcheck への prompt 入力と出力。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:230-254` — spec-check の prompt 利用、一致比較と終了コード `3`。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:257-264` — benchmark の prompt 利用と出力。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:267-284` — parallel sweep が prompt 列を反復して初期 token に使う処理。
- `engine/src/inkling2/sycl/ink_sy_runner.h:421-427,454-470` — `forward_batch` の入力 token を device に転送し embedding kernel を呼ぶ箇所。
- `engine/src/inkling2/sycl/ink_sy_ops.h:18-42` — embedding kernel が token ID を行の添字に使う箇所。明示的な token ID 範囲検査はない。
- `docs/cli/README.md:1572-1592` — `strata-inkling-sycl` のコマンド階層と、このオプションの索引上の scope・alias。

調査対象は上記 commit の Strata checkout 内ソースに限定した。SYCL バイナリの `--help` は実行しておらず、実機での GPU エラー挙動は確認していない。
