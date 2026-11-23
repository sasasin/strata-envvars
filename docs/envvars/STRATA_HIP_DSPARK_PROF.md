# `STRATA_HIP_DSPARK_PROF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP backend の `InkHipBackend::dspark_draft` で、DSpark の処理区間を HIP event で計測して stderr に出力する診断用スイッチ。値が正数として解釈されると、計測 event を作成・記録し、成功した draft 呼び出しの最後に区間時間を表示する。また同じ条件で `use_ds_graph` が false になるため、条件を満たせば通常選択される HIP graph の capture / launch 経路を使わず、通常の kernel launch 経路を通る。DSpark draft を有効化するスイッチではなく、draft の可否は backend・モデル・`--draft` によって別に決まる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1603-1608,1621-1625,1766-1776`; `engine/src/inkling2/ink_serve.h:441-446,812-816`）。

## 値と判定

HIP の `dspark_draft` が scratch 確保とヘッダー転送を通過した後、`getenv` を呼び、値が存在するときだけ `atoi` の結果が 0 より大きいかを判定する。文字列全体の検証や範囲検査はなく、`atoi` が先頭から読み取った整数部分で判定される。設定されているだけでは有効にならず、空文字・数値に変換できない先頭・ゼロ・負数は false になる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1596-1604`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| HIP `dspark_draft` が判定箇所まで到達 | `ds_prof=false`。計測せず、graph 適用条件が揃えば graph 経路を選択 | `1`, `2`, `+1`, ` 1`, `1abc`, `1.5`（`atoi` が正数を返す） | 空文字、`0`, `0anything`, `-1`, `true`, `false`, `abc`, `  ` |

`atoi` は 10 進数整数の先頭部分を読むため、先頭の空白や符号は許容され、後続の非数字は判定対象にならない。大文字小文字は関係しない。整数として表現できない範囲の値については、コードに明示的な境界処理がなく、挙動を保証できない。`getenv` と `atoi` の結果は関数内のローカル `const bool` にだけ保持される（同:1603-1604）。

## 有効になる条件

- Strata が HIP backend をビルドして実行し、`dspark_draft` が呼ばれること。通常 backend 選択は `INKLING_ENABLE_HIP` のビルド分岐による（`engine/src/inkling2/ink_backend.h:150-165`）。他 backend にある同名変数の読み取りはない。
- サーバーループで `draft_mode != "off"`、モデルに DSpark データがあり、backend が `dspark_ready()` を返すこと。HIP backend 側では `opts.enable_dspark && dspark_cfg_.present` のとき `has_dspark_` が立つ（`engine/src/inkling2/ink_serve.h:441-446`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:515,854-855`）。`--draft off` は `enable_dspark` を false にする（`engine/src/inkling2/ink_main.cpp:428-432`）。
- さらに slot が有効、anchor 位置が有効、`max_draft > 0` であり、scratch 準備とヘッダー転送に成功して判定箇所へ到達する必要がある。これらを満たさない場合は環境変数を判定せず 0 を返す（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1555-1562,1596-1603`）。
- 値が正数でも DSpark は止まらない。graph を使わないことで profiling 区間を event で囲める。値が無効なら profiling event は作らず、graph 側は draft 数・事前ロード済み重み・head dimension 等の条件が揃ったときだけ使われる（同:1603-1625）。
- CLI の `--draft` は DSpark の有効化を決める別設定で、この環境変数との上書き優先順位はない。別の環境変数との組み合わせもコード上にない。

## 実行時の詳細

読み取りはプロセス起動時の一括設定や static cache ではなく、`dspark_draft` の各呼び出しで、その呼び出しが判定箇所に達するたび行われる。コード上は `getenv` を式中で 2 回呼ぶ。したがって、起動後に環境値を変更した場合も次の呼び出し時に再評価される。ただし最初の `getenv` が非 null で、2 回目が null になるような同時変更を扱う保護はこのコードにない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1603`）。

正数の場合は 4 個の HIP event の作成と開始 event の記録を試み、DSpark block の生成、3 層計算後、screen 後、Markov 後の各位置で event を記録する。D2H 転送と stream 同期に成功した後、`tot`, `3L`, `screen`, `markov` の経過時間を計算して 1 行出力し、event を破棄する。event API の戻り値は無視されるため、event 操作自体の失敗はこのコードではエラーとして報告されない。計測ログは、この呼び出しが途中のエラー return に入らず成功経路を完了した場合に限って出る（同:1621-1625,1697,1712,1748,1762-1775）。

graph 経路が使われる条件を `!ds_prof` が明示的に含むので、有効値では graph capture / launch を行わない。無効値の場合でも graph 条件が欠ければ通常 kernel launch を使う。検査付きの HIP 処理が失敗すると `dspark_draft` は 0 を返し得る。サーバー側は `nd > 0` の場合に限って draft 候補の検証経路へ進む（同:1604-1619,1762-1776; `engine/src/inkling2/ink_serve.h:813-828`）。

## ログと測定値

成功経路では stderr に次の形式で出力する。各数値は HIP event の elapsed time をミリ秒単位で表示するコードだが、特定環境での実測性能値を示すものではない。

```text
[DSPARK-PROF] K=%d pos=%d tot=%.2fms | 3L=%.2f screen=%.2f markov=%.2f
```

`K` はその呼び出しで作る draft 数、`pos` は anchor 位置。`tot` は最初から最後の event、`3L`・`screen`・`markov` は対応する event 区間である。値が未設定または正数でない場合、この行も event 計測も行わない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1621-1625,1697,1712,1748,1766-1775`）。

## 根拠

- 直接読み取り、整数判定、graph 条件: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1596-1608`
- backend の有効条件と早期 return: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:515,854-855,1555-1562`
- event の記録、同期、ログ: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1621-1625,1697,1712,1748,1762-1776`
- HIP backend 選択と DSpark CLI / server 条件: `engine/src/inkling2/ink_backend.h:150-165`; `engine/src/inkling2/ink_main.cpp:428-432`; `engine/src/inkling2/ink_serve.h:441-446,812-828`
