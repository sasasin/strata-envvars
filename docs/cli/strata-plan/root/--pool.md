# `--pool`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan` |
| オプション | `--pool` |
| 別名 | なし |
| 値 | 10 進整数（byte 数として `uint64_t` に変換） |

## 役割

`strata-plan` の VRAM 容量入力を指定します。ただし値は `make_plan` に渡す共有 pool 容量そのものではなく、`--vram` と共用する free VRAM 入力です。後段で `--dense` と `--embd` の値を差し引いてから計画関数へ渡します。`strata-plan` は GPU を起動せず、指定された容量とモデル幾何からメモリ計画を表示する CLI です（`src/plan/plan_main.cpp:1-5,40-43,59-67`）。

## 使い方

```sh
strata-plan --pool 12000000000 --dense 4000000000 --embd 1000000000
```

この例では `--pool` が設定する入力から dense weight と embedding の各 byte 数を差し引き、その結果を計画関数へ渡します。値の単位は byte です（`src/plan/plan_main.cpp:31-43,59-66`）。

## 値と既定値

- 値は必須です。値が後続にない場合は stderr に `--pool needs a value` を出して終了コード 2 で終了します（`src/plan/plan_main.cpp:20-24,40-43`）。
- 値は `std::strtoull(..., nullptr, 10)` で変換されます。明示的な範囲確認、変換エラー確認、末尾文字の確認はありません。したがって不正な文字列や範囲外値を CLI が拒否する保証はありません。変換後の値の具体的な挙動は C ライブラリの `strtoull` に従います（`src/plan/plan_main.cpp:20-25`）。
- `--pool` 単独の既定値はありません。未指定時は `free_vram` が 12,000,000,000 byte で初期化されます（`src/plan/plan_main.cpp:14-16`）。
- `--pool` を `--vram` と複数回指定した場合、両方とも同じ変数を設定するため、引数列で最後に現れた方が残ります。`--pool` の複数指定も同様に最後の値が残ります（`src/plan/plan_main.cpp:18-30,40-43`）。

## 実行時の動作

1. parser は `--pool` の次の引数を 10 進変換し、`free_vram` に代入します（`src/plan/plan_main.cpp:20-25,40-43`）。
2. parser 処理後、`free_vram` が `dense_bytes + embd_bytes` より大きい場合はその合計を差し引きます。等しいか小さい場合は中間 pool を 0 とします（`src/plan/plan_main.cpp:59-63`）。
3. 中間 pool が 0 の場合、計画関数には `strata::plan::vram_pool_bytes()` の 5,943,000,000 byte が渡されます。つまり `--pool 0` や `--pool` の値が dense・embedding 合計以下の場合、値を直接 0 byte として扱わず、この固定値へフォールバックします（`src/plan/plan_main.cpp:61-66`; 固定値は `include/strata/plan/plan.hpp:122-127`）。
4. `make_plan` は受け取った pool を VRAM budget とし、KV・indexer cache の容量と、dense、embedding、MTP、workspace、state の固定費を検査します。固定費と KV 容量が pool を超えると計画は失敗します（`include/strata/plan/plan.hpp:129-149`）。

`--dense` と `--embd` は `free_vram` からの差し引きに使われ、さらに `make_plan` 内の固定費にも含まれます。この二段階の扱いはソースにそのまま実装されています。特にこれらを非ゼロで指定した場合は、`--pool` 入力から差し引いた後の budget にも同じ値が固定費として計上されるため、十分な値を見積もる必要があります（`src/plan/plan_main.cpp:31-34,59-66`; `include/strata/plan/plan.hpp:136-145`）。

## 適用条件と副作用

このオプションは `strata-plan` の計画計算だけに適用され、コード上は GPU、ネットワーク、ファイル、子プロセスを操作しません。`--pool` は実測 GPU memory を取得せず、与えた数値を `--vram` と同じ入力欄に設定します（`src/plan/plan_main.cpp:1-5,40-43,59-67`）。

## 出力とエラー

- 成功時は `strata::plan::to_string` の計画を stdout に出し、終了コード 0 を返します（`src/plan/plan_main.cpp:64-68`; 出力形式は `include/strata/plan/plan.hpp:154-165`）。
- 必要な固定費と KV 容量が pool を超える場合、`DoesNotClose` のメッセージを `strata-plan: ...` の形で stderr に出し、終了コード 1 を返します。メッセージは必要 byte 数と pool byte 数を示し、`--max-context` を減らすよう案内します（`include/strata/plan/plan.hpp:138-143`; `src/plan/plan_main.cpp:69-72`）。
- 1 slot 分の expert cache を確保できない場合も `DoesNotClose` となり、上記と同じ catch 経路で終了コード 1 になります（`include/strata/plan/plan.hpp:144-150`; `src/plan/plan_main.cpp:69-72`）。
- 値を欠落させた場合は前述のとおり stderr に `--pool needs a value` を出し、終了コード 2 で終了します（`src/plan/plan_main.cpp:20-24,40-43`）。

## 根拠

- parser、値変換、`--vram` との共用、エラー経路、容量計算呼び出し: `src/plan/plan_main.cpp:13-73`
- pool の導出、固定費判定、計画失敗: `include/strata/plan/plan.hpp:122-151`
- 共有 pool 容量と計画表示: `include/strata/plan/plan.hpp:122-127,154-165`
- `strata-plan` の build target: `CMakeLists.txt:330-331`

同一 revision の既存 CLI バイナリは確認・実行していません。本文は parser と利用箇所のソース調査に基づきます。
