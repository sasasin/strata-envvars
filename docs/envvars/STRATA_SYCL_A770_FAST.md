# `STRATA_SYCL_A770_FAST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の router と host-mapped memory の一部転送で、fast 実装を選ぶ opt-in フラグ。実行時にこの値を読むのは `strata::a770_fast()` で、router の dispatch、doorbell payload の activation 書き込み、mapped memory からの `float4` 読み出しへ bool が渡される。変数名に A770 とあるが、読み取り側に GPU 名による制限はない。実際に各 fast 分岐へ入るかは下記の shape・device 条件に従う（`engine/sycl/include/strata/sycl_doorbell.hpp:22-26`, `engine/sycl/src/kernels/cuda/router_top10.dp.cpp:817-833`, `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:603-623,745-777`, `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2867-2888`）。

router fast 分岐は通常 router の選択 kernel を `launch_sycl_fast<false>` に切り替える。mapped payload の場合は activation の隣接 2 個の `float` を 64-bit store にまとめ、読み出し側では `float4` を 2 回の 64-bit load で取得する。doorbell の tag/checksum と payload の word 順は維持する。一方、doorbell の `plain` 書き込み、8-byte 非整列出力、奇数個の activation の末尾は scalar store に戻る（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:582-623`; `engine/sycl/include/strata/sycl_doorbell.hpp:29-45`）。

## 値と判定

`std::getenv` の結果が null でなく、かつ先頭文字が ASCII `'1'` の場合だけ true。数値や文字列全体は parse・比較しない。空文字は設定済みでも false。大文字小文字や後続文字は見ず、先頭より前の空白を飛ばさない（`engine/sycl/include/strata/sycl_doorbell.hpp:23-25`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `strata::a770_fast()` の読み取り | false | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `-1` |

## 有効になる条件

- 対象コードが SYCL engine に組み込まれ、該当する router / mapped-memory / doorbell 経路が呼ばれること。CUDA/HIP engine や、これらの SYCL 関数を通らない処理にはこの読み取りの効果はない。
- router fast dispatch は `n_tokens > 0`, `64 < n_expert <= 512`, `0 < k <= 32` が必要。ただし先行する `!device_has_fp64` 分岐に該当すると、FP32 router を起動して先に return するため、この fast router 分岐には入らない。実装コメントは Intel Arc A-/B-series を FP64 非対応としている。従ってこの router fast 分岐は、少なくともコメント上の A770 条件では選択されず、FP64 対応 device で前記 shape を満たす場合に選択される（`engine/sycl/src/kernels/cuda/router_top10.dp.cpp:433-440,553-563,817-833`）。
- doorbell の activation pair store は `pair=true` のほか `plain=false` と出力 pointer の 8-byte alignment が必要。`STRATA_DOORBELL_PLAIN` の先頭文字が `'1'` なら `doorbell_plain_payload()` は true。未設定時も driver 名が `i915` なら true となり、この pair store を迂回する。出力サイズが奇数なら最後の要素は scalar で処理される（`engine/sycl/include/strata/sycl_doorbell.hpp:104-113`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:603-623,745-777`）。
- `copy_or_zero_from_mapped` は bool を kernel に渡すが、mapped read は skip flag が一致してゼロ化する場合を除く。pair 時は `load_mapped_float4` を使う（`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2767-2782,2867-2888`; `engine/sycl/include/strata/sycl_doorbell.hpp:40-45`）。
- `doorbell_publish_res` のカーネルは `STRATA_DOORBELL_CHECK` が unset または先頭文字が `'1'` 以外の場合、`full=false` の経路で resident 判定と必要時の scalar copy を行い、`pair` を activation copy に使わない。`STRATA_DOORBELL_CHECK` の先頭文字が `'1'` の場合は full payload 経路となり、pair store 条件も適用される。他の `doorbell_publish` / `doorbell_publish_value` の pair store にはこの check 条件はない（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:676-719,800-826`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:803-804`）。
- この環境変数が要求する追加の CLI 引数、サーバーモード、モデル形式の条件はコード上で見つからない。router shape と呼び出し経路、上記 payload 条件が適用条件となる。

## 実行時の詳細

`a770_fast()` は関数内 `static const bool` を初回呼び出し時に初期化する。初回呼び出しより後にプロセス環境を書き換えても値は更新されない。helper は header の inline 関数で、参照箇所は通常 router、doorbell の3 publish 関数、mapped `copy_or_zero_from_mapped`。`STRATA_SYCL_A770_FAST` 自体を読む箇所はこの helper だけである（`engine/sycl/include/strata/sycl_doorbell.hpp:23-25`; `engine/sycl/src/kernels/cuda/router_top10.dp.cpp:828`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:745-777,800-806`; `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2871`）。

有効時の fast router は `router_top10` の該当 dispatch で `launch_sycl_fast<false>` を起動し、null stream なら queue を待つ。router 分岐が使われない場合は従来の device 条件に対応する router のまま。doorbell payload では activation 値を隣接 2 個ずつ store し、checksum には各 32-bit word と元の位置を個別に加算するので、pair store 自体が checksum の word/position 順を変えない。mapped read は `float4` を二つの 64-bit word として取得し、元の4要素の並びに戻す（`engine/sycl/src/kernels/cuda/router_top10.dp.cpp:817-833`; `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:582-623`; `engine/sycl/include/strata/sycl_doorbell.hpp:40-45`）。

この変数による有効・無効ログはない。`elementwise.dp.cpp` の `check_launch` は常に true を返す実装で、CUDA の launch error code 検査に相当する処理をしていない。router は null stream の場合に `q.wait_and_throw()` を呼ぶが、この dispatch 自体に専用の catch・ログ・fallback はない。対象設定の値に応じた専用エラーや fallback log は確認できない（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:196-205`; `engine/sycl/src/kernels/cuda/router_top10.dp.cpp:542-550,828-832`）。

## ログと測定値

`docs/A770_SPEED_SPEC.md` は旧 baseline `501f675727ae8a54abed3ec467de1cbfbecd03ea` 時点の記録として、fast router 単体の 256-expert/top-10 timing が 395.47 から 118.62 microseconds/call、最終構成の decode が 13.5/11.9/12.3 tok/s と記載する。文書自身が目標達成を主張しておらず、この資料の revision は本調査対象と異なるため、現行 HEAD での測定値とは扱わない。現行コードでは前述の FP64 条件により A770 の通常 router 呼び出しが先行 FP32 経路へ進む点にも注意が必要（`docs/A770_SPEED_SPEC.md:31-59`; `engine/sycl/src/kernels/cuda/router_top10.dp.cpp:817-833`）。

## 根拠

- `engine/sycl/include/strata/sycl_doorbell.hpp:22-45,104-113` — 値の読み取り、cache、mapped 64-bit read、plain store 判定。
- `engine/sycl/src/kernels/cuda/router_top10.dp.cpp:433-440,553-563,817-833` — FP32 router の先行 dispatch と fast router の shape 条件。
- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:582-623,647-719,745-826` — paired activation publish、checksum 維持、3 publish 経路の引き渡し。
- `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2767-2782,2867-2888` — mapped read の pair 条件。
- `docs/A770_SPEED_SPEC.md:31-59` — 旧 revision の測定記録と baseline。
