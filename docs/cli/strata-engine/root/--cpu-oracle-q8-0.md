# `--cpu-oracle-q8-0`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（CMake 生成の推論エンジン。`strata-terminal` の wrapper とは別） |
| オプション | `--cpu-oracle-q8-0` |
| 別名 | なし |
| 値 | 値を取らない boolean フラグ。指定すると有効。既定値は `false`（無効） |

## 役割

CPU expert の活性値量子化と Q2_0 dot reduction に、ソースコメントが「pinned x86 / llama.cpp-CPU-exact」と呼ぶ Q8_0 oracle 経路を選びます。CPU expert の数値経路を比較・固定するための実験用フラグです。help も実験的な CPU expert quantization / dot reduction と説明しています（`src/program/generate.cpp:855`）。

## 使い方

```sh
strata --pack ./model.strata --cpu-oracle-q8-0 --tokens 1,2,3
```

ここでは pack を読み、token ID `1,2,3` を入力する例です。`--pack`、`--tokens` と本フラグは同じエンジン parser の引数です（`src/program/generate.cpp:2425-2442`）。

## 値と既定値

- 値や追加引数は不要です。parser は指定時に `o.cpu_oracle_q8_0 = true` とし、フラグ未指定時は options 構造体の初期値 `false` のままです（`src/program/generate.cpp:467`, `src/program/generate.cpp:2499`）。
- 同じフラグを複数回指定した場合も同じ boolean を `true` にするだけで、追加動作はありません（`src/program/generate.cpp:2499`）。
- parser にこのフラグ固有の値 validation はありません。

## 実行時の動作

起動時の整合性確認後、エンジンは `expert_set_oracle_q8_0(o.cpu_oracle_q8_0)` を呼び、CPU expert 側で参照する process-wide atomic flag を設定します（`src/program/generate.cpp:3407-3415`; `src/kernels/cpu/expert_layout.cpp:299-310`）。

有効時、CPU expert の第一段・第二段の活性値を `quantize_oracle_q8_0` で量子化し、oracle の row-dot を使います。実装は各 chunk の絶対値最大を求め、scale を最大値 / 127 とし、値を丸めて int8 code にします。その後 gate/up の dot、SiLU gate と up の積、第二活性の量子化、down projection の dot の順で処理します（`src/kernels/cpu/expert.cpp:75-110`, `src/kernels/cpu/expert.cpp:323-335`, `src/kernels/cpu/expert.cpp:341-345`, `src/kernels/cpu/expert.cpp:408-430`）。

この oracle 経路には multi-token expert kernel がないため、有効時は複数 token 用の CPU expert 関数も token ごとの単一経路にフォールバックします。また expert pool の `run_split` は通常の split 処理を迂回して `run` を呼び、`run_split_multi` も単一 token job に展開します（`src/kernels/cpu/expert.cpp:561-566`, `src/kernels/cpu/pool.cpp:1300-1303`, `src/kernels/cpu/pool.cpp:1320-1335`）。したがってこのフラグで性能が上がるとはソースからは言えません。コメントには特定のベンチ測定で oracle が pool time を増やした記録がありますが、他環境での性能予測には使えません（`src/program/generate.cpp:3283-3284`）。

## 適用条件と副作用

- `--expert-cache` の値が 0 以外、または `--expert-profile` が指定されている場合は併用できません。GPU expert contract が一致するまでの制約として、エンジンはエラーメッセージを stderr に出して終了コード 2 で拒否します（`src/program/generate.cpp:3407-3409`）。
- `--native` preset はこのフラグを自動的には有効化しません。該当箇所のコメントは、native preset では CPU expert は通常 VNNI kernel のままで、明示的な `--cpu-oracle-q8-0` が oracle を選ぶと記しています（`src/program/generate.cpp:3283-3285`）。
- Apple Metal build については同じ起動処理でフラグを設定しますが、その分岐のコメントは expert が GPU 上で実行されるとしています。CPU oracle の実行経路が適用されるかは、確認したこの箇所だけでは断定できません（`src/program/generate.cpp:3415-3425`）。
- このフラグは session configuration fingerprint の `cpu_oracle_q8_0` switch に含まれます。該当する session identity では有効・無効が設定差として扱われます（`src/program/generate.cpp:9450-9462`）。
- 通常 build の起動時には CPU expert kernels に必要な AVX2 + FMA + F16C がなければ、CPU 名と要件を stderr に出して終了コード 2 で拒否します。これはフラグ専用の validation ではなくエンジンの起動条件です。Apple Metal および `STRATA_ISA_FLOOR` を使う older-CPU build には別分岐があります（`src/program/generate.cpp:3416-3448`）。oracle の ISA 条件はビルド構成にも関係するため、確認していない build / CPU 組み合わせの可否は断定しません。

## 出力とエラー

このオプション単独では成功時に専用メッセージを出しません。`--expert-cache` または `--expert-profile` と競合すると、`strata generate: --cpu-oracle-q8-0 cannot be combined with --expert-cache or --expert-profile until the GPU expert contract matches` を stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:3407-3409`）。

## 根拠

- `src/program/generate.cpp:467, 855, 2499` — option の既定値、help 表記、parser。
- `src/program/generate.cpp:3407-3448` — expert cache/profile との拒否、CPU oracle 設定、CPU/ISA 起動条件。
- `src/program/generate.cpp:3283-3285` — `--native` preset と oracle の関係。
- `src/kernels/cpu/expert.cpp:75-110, 323-335, 341-345, 408-430, 561-566` — oracle quantization、二段 expert 計算、multi-token fallback。
- `src/kernels/cpu/expert_layout.cpp:299-310` — process-wide atomic flag。
- `src/kernels/cpu/pool.cpp:1300-1303, 1320-1335` — expert pool の分岐。
- `src/program/generate.cpp:9450-9462` — session configuration fingerprint への記録。
- 索引上の scope は `docs/cli/README.md:1128-1156` に記載された `strata-engine/root` です。SYCL variant にも同じ option 名、初期値、競合確認、flag 設定があります（`sycl/src/program/generate.cpp:450, 784, 1840, 2573-2581`）。本書の動作追跡は索引が指定する通常の `src/program/generate.cpp` と CPU kernel 実装を対象にしました。
