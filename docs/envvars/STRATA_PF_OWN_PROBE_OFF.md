# `STRATA_PF_OWN_PROBE_OFF`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

HIP build の integrated GPU で、cache slot を借りずに prompt path 自身の buffer を確保する大きな chunk を使うとき、Strata が起動時に行う UMA launch probe を省略します。これは chunk サイズを選ぶ変数ではなく、probe の直前に probe を止める環境変数です。参照は `src/program/generate.cpp` の `uma_refuse_chunk_if_full()` だけです（1924-1940 行）。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 他の条件を満たせば probe を実行 |
| 空文字を含む、何らかの値が設定済み | probe を省略 |

文字列の内容、数値、先頭文字は読みません。`std::getenv(...) != nullptr` という設定有無だけの判定です。そのため `0` や空文字でも省略します。fallback 値や無効値処理はありません（`src/program/generate.cpp:1929`）。

この環境変数は chunk を変えず、`--prefill` または自動 chunk 選択で決まった値を上書きしません。chunk 選択側では `--prefill auto:N` と `STRATA_PREFILL_AUTO_MAX` を別に読み取ります（`src/program/generate.cpp:3526-3534`）。

## 有効になる条件

変数が未設定でも、次の条件をすべて満たす場合にだけ probe が実行されます。

- Strata が `STRATA_USE_HIP` 定義付きでビルドされている。HIP 以外では関数は即時 return し、この環境変数は読まれません（`src/program/generate.cpp:1924-1929`）。
- prompt path が cache slot を借りていない（`borrows == false`）。
- 選択済み chunk が 16384 tokens より大きい。16384 以下は対象外（`src/program/generate.cpp:1929`）。
- `spill_discrete_gpu()` が false、すなわち Strata の判定上 discrete GPU ではない。HIP/CUDA runtime の device property の `integrated` を使って判定します（`src/program/generate.cpp:277-288`）。

実装コメントは Strix Halo で観測した問題として説明していますが、コードに特定 GPU 型の追加判定はありません。したがって上記条件に合う HIP integrated GPU がコード上の適用範囲です。cache slot を借りない prompt path では、buffer を割り当てた後、この判定関数が serve と generate の両経路から呼ばれます（`src/program/generate.cpp:11134`, `19721-19730`）。

## 実行時の詳細

環境変数は `uma_refuse_chunk_if_full()` が呼ばれるたびに `getenv()` で評価され、static cache には保存されません。関数呼び出し前にプロセス環境を書き換える場合、その呼び出しでは新しい設定有無が判定に使われます（`src/program/generate.cpp:1924-1929`）。

probe は prompt path の buffer 初期化後、prompt を読む前に実施されます。Strata は 64 MiB を確保し、non-blocking stream を作成し、その領域をゼロ埋めして stream 同期まで試します。probe 成功時は通常そのまま続行し、`STRATA_TRACE` が設定されていれば stderr に `strata trace: the launch probe passed with a ...-token chunk` を出します（`src/program/generate.cpp:1903-1915,1930-1934`）。

probe 失敗時、Strata は理由を含む `strata generate: a ...-token prompt chunk does not fit beside the ... GiB expert cache on this GPU (...): use --prefill auto:..., or a smaller --expert-cache` を stderr に出して flush し、終了コード 2 でプロセスを終了します（`src/program/generate.cpp:1935-1939`）。理由は 64 MiB 確保失敗、stream 作成失敗、または fill/sync/launch 失敗のいずれかです（`src/program/generate.cpp:1903-1915`）。環境変数を設定すると、この probe とそれに由来するこの失敗経路をスキップします。以後の GPU 呼び出しが成功することまでは保証しません。

## 根拠

- 変数の唯一の読み取りと条件分岐、失敗時のログ・終了: `src/program/generate.cpp:1924-1940`
- UMA probe の割り当て、stream、fill/sync、失敗理由: `src/program/generate.cpp:1900-1917`
- discrete/integrated GPU 判定: `src/program/generate.cpp:276-289`
- serve / generate での呼び出し位置: `src/program/generate.cpp:11134`, `19721-19730`
- chunk 選択時の `--prefill` / `STRATA_PREFILL_AUTO_MAX` 読み取り: `src/program/generate.cpp:3526-3534`
