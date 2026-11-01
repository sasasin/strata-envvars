# `STRATA_ESIMD_LV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL の Battlemage 向け QSA prompt attention ESIMD kernel で、Q/K と P/V の int8 分割量子化レベル数を選びます。値は同じ kernel 内の `launch<QL, PL>` テンプレート引数に変換されます。これは kernel の数値計算経路を選ぶ設定で、別経路の prompt attention を有効化する設定ではありません。

## 値と判定

値は `std::atoi` で整数に変換されます。文字列全体の検証、範囲検査、clamp はありません。変換結果に応じた選択は次のとおりです。

| 環境値 | `atoi` の結果 | 起動する組合せ `(QL, PL)` |
|---|---:|---|
| 未設定 | 既定値 `2` | `(2, 2)` |
| `3` | 3 | `(3, 3)` |
| `32` | 32 | `(3, 2)` |
| `23` | 23 | `(2, 3)` |
| 上記以外 | 変換結果を問わず | `(2, 2)` |

空文字や数字で始まらない文字列は `atoi` により 0 となり `(2, 2)` を選びます。先頭の空白や符号は `atoi` の整数変換規則に従い、整数の後ろにある文字は判定されません（例: `3junk` は 3 となり `(3, 3)`）。負数も特別扱いされず `(2, 2)` です。整数型で表せない範囲の入力については実装に検証処理がありません。

## 有効になる条件

この環境変数は、SYCL 実装の `qsa_prompt_attn_esimd()` が実行対象になったときだけ読み取られます。呼び出し元は先に ESIMD 経路を試し、実装が `false` を返した場合は XMX 経路を試し、それも受け付けなければ従来 kernel に戻ります（`sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2013-2015`）。

ESIMD 経路では、別環境変数 `STRATA_PROMPT_ATTN_ESIMD` が `atoi` で 0 になる場合、`n_q <= 0`、pool の形式や shape が対応条件に合わない場合、page size が正の 2 冪でない場合、または現在の device が Battlemage でない場合に `false` を返し、`STRATA_ESIMD_LV` には到達しません。該当する条件を通過して kernel が起動されると、この変数の値が反映されます（`sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:405-435`）。

この実装は `#ifndef STRATA_I8_NO_ESIMD` の範囲にあり、ESIMD を無効化したビルドでは同じ関数が常に `false` を返す stub になります。SYCL ビルド設定では `STRATA_SYCL_I8_ESIMD` によって ESIMD kernel の採否が制御されます（`sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:37-38,440-443`; `sycl/CMakeLists.txt:50-63,248`）。

## 実行時の詳細

読み取り箇所は `qsa_prompt_attn_esimd()` 内の1箇所です。関数の適用条件を通過した後、最初の適用可能な呼び出しで `static const int` として評価・保存されます。その後プロセス内で環境を変えても再評価されません。CLI 引数、設定ファイル、他の変数による `STRATA_ESIMD_LV` の上書きはこのコードにはありません。

`QL` は Q/K の積の int8 分割レベル数、`PL` は P/V の積の分割レベル数です。レベル分割は `split_lv` で各レベルの int8 値を作り、積をレベル係数で合成します。したがって `3`, `32`, `23` は、それぞれ両方を3段、Q/Kのみ3段、P/Vのみ3段にする選択です（`sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:66-78,154-170,187-212,237-255,419-435`）。

この変数専用のログ、警告、無効値エラーはありません。ESIMD 経路が選ばれたときは stderr に `strata: prompt attention on the int8 DPAS (ESIMD)` を一度出しますが、選択されたレベル値は表示しません（`sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:416-419`）。条件不一致による `false` は呼び出し元の別経路への fallback になります。レベル設定による終了・失敗経路はコード上確認できません。

## 根拠

- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:405-435` — `STRATA_PROMPT_ATTN_ESIMD` の既定値と停止判定、shape・device 条件、ログ、`STRATA_ESIMD_LV` の既定値・変換・分岐・kernel 起動。
- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:66-78,138-170,187-255,285-320` — Q/K と P/V における分割レベル数と合成計算。
- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:37-38,440-443`; `sycl/CMakeLists.txt:50-63,248` — ESIMD 実装の compile-time 条件と SYCL kernel の登録。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2013-2015` — ESIMD、XMX、従来 kernel への fallback 順。
- `sycl/include/strata/kernels/qsa_prompt_attn_esimd.hpp:7-10` — 対応しない device・shape・pool で何も launch せず `false` を返す契約、および ESIMD 経路の既定有効・停止用変数。
