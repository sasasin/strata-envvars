# `STRATA_BATCH_GDN_GROUPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

複数 slot の batch window における GDN recurrence を、slot ごとの呼び出しから複数 slot をまとめた `gdn_step_norm_groups` の呼び出しへ切り替える。CUDA/HIP 共通実装では window 内の recurrence と、条件を満たす commit 時の recurrence の両方が対象で、SYCL にも同種の分岐がある。GDN convolution の commit は引き続き slot ごとに行われる。通常の単独 slot の window にはこの環境変数による切り替えはない（`engine/src/core/verify.cpp:1978-2007, 4739-4773`、`engine/sycl/src/core/verify.cpp:1277-1305, 3427-3463`）。

## 値と判定

読み取りは `getenv` の結果を `std::atoi` に渡し、結果が 0 でないかを判定する。値全体の検証はしない。したがって未設定、空文字、`0`、`0anything`、`true`、数字で始まらない文字列は無効になる一方、`1`、`-1`、` 1`、`1anything` は有効になる。先頭の空白と符号は `atoi` の規則に従い、数字列の後ろは判定に使われない。整数としての範囲検査や無効値警告はない。CUDA/HIP では `env_nonzero` 経由、SYCL では同じ `getenv` と `atoi` の判定を個別に行う（`engine/src/core/verify.cpp:375-377, 391-392`、`engine/sycl/src/core/verify.cpp:1278-1281, 3427-3430`）。

unset 時の既定値は実行条件で異なる。起動時の既定値設定は環境変数が存在するかだけを確認し、空文字や `0` を含め、利用者が設定した値を残す（`engine/src/core/arch_defaults.cpp:218-245, 253-260, 302-310, 346-356, 433-442`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux CUDA build、`--batch` が 2 以上 | 起動時に `1` を設定する | `1`, `-1`, `1x` | `0`, `0x`, 空文字 |
| HIP の離散 RDNA3 並列 stack（batch slot が 2 以上）で `STRATA_GFX11_DEFAULTS=0` / `STRATA_DEFAULTS=026` による無効化がない場合。または Windows gfx1151 で batch slot が 2 以上かつ `STRATA_GFX1151_DEFAULTS=0` でない場合 | 起動時に `1` を設定する | `1`, `-1`, `1x` | `0`, `0x`, 空文字 |
| 上記以外（SYCL、Metal、その他の CUDA/HIP 構成、batch slot が 2 未満を含む） | `atoi` 判定では 0、OFF | `1`, `-1`, `1x` | `0`, `0x`, 空文字 |

## 有効になる条件

- GDN 層を含むモデルで、engine が batch window を capture する経路に入る必要がある。window 外の通常の recurrence ではこの switch を参照しない（`engine/src/core/verify.cpp:1978-2007`、`engine/sycl/src/core/verify.cpp:1277-1305`）。
- window 内の CUDA/HIP recurrence は `batch_rec_` が有効で、現在の slot row 群の長さ `te - tb` が 8 以下の場合に grouped kernel へ進む。条件を満たさない場合は slot ごとに `gdn_step_norm_multi` を呼ぶ（`engine/src/core/verify.cpp:1978-2004`）。SYCL も `batch_rec_` と `te - tb <= 8` を要求する（`engine/sycl/src/core/verify.cpp:1277-1305`）。
- 通常の commit graph の切り替えは、window の行数が 8 以下で、隣り合う row がすべて異なる（各 slot が 1 row）場合だけ行う。`--batch-mtp` の proposal row を含む同一 slot の複数 row がある場合は grouped commit を使わない。pipelined window が verdict 後に commit する deferred 経路では `capture_commit_batch` を呼ばない。conv commit はどちらの場合も slot ごとのまま（`engine/src/core/verify.cpp:4710-4713, 4741-4767, 4830-4855, 5310-5312`、`engine/sycl/src/core/verify.cpp:3431-3457`）。
- 対応 build ごとの実装は CUDA/HIP 共通の `engine/src/core/verify.cpp` と SYCL の `engine/sycl/src/core/verify.cpp`。名前の直接読み取りや Strata による既定値設定が確認できない Metal 経路では、この変数の効果を確認できない。
- Linux CUDA は `--batch >= 2` なら既定値を適用する。HIP では離散 RDNA3 で `STRATA_GFX11_DEFAULTS=0` または `STRATA_DEFAULTS=026`、Windows gfx1151 で `STRATA_GFX1151_DEFAULTS=0` が既定値の適用を止める。その他の未設定値は OFF（`engine/src/program/generate.cpp:4287-4320, 4410-4414`、`engine/src/core/arch_defaults.cpp:240-260, 302-310, 346-356, 433-442`、`engine/include/strata/core/gfx11_extra.hpp:27-30, 116-132`）。
- CLI 引数でこの変数を直接指定する仕組みは見つからない。`--batch` は CUDA/HIP の一部構成で既定値を適用する条件として使われる。HTTP server は `cfg.env` の項目を文字列化して child engine に渡し、この変数固有の追加・上書きはしない（`terminal/serve/server.py:4007-4028`）。

## 実行時の詳細

CUDA/HIP 共通実装は関数内 `static const bool` に結果を保存し、最初に参照した時点の値をプロセス内で使い続ける。起動時の arch defaults はこの初回参照より前に実行されるよう配置されている。Linux CUDA の defaults 適用は `generate.cpp`、HIP のものは `STRATA_USE_HIP` の初期化ブロック内から行う（`engine/src/core/verify.cpp:373-392`、`engine/src/program/generate.cpp:4287-4320, 4410-4414`）。

SYCL は window recurrence と commit の各コード位置に関数内 static cache を持つため、それぞれ最初の実行時に読み取る（`engine/sycl/src/core/verify.cpp:1277-1281, 3427-3430`）。どの実装でも、cache 後に環境を書き換えても判定は更新されない。CUDA/HIP では同じ batch window の graph も layout ごとに capture 後再利用される（`engine/src/core/verify.cpp:4677-4684, 4710-4713, 5302-5312`）。

群化した recurrence は各 row の GDN state と row 範囲を `GdnGroups` に集め、`gdn_step_norm_groups` で計算する。CUDA/HIP の window 内では grouped 呼び出しにより各 row の `y_` が出力され、commit では recurrence state を更新する。条件に合わない場合は既存の per-slot recurrence 経路へ進む（`engine/src/core/verify.cpp:1978-2007, 4743-4773`）。SYCL でも同じ grouped kernel 関数を window と commit で呼び分ける（`engine/sycl/src/core/verify.cpp:1282-1305, 3433-3463`）。

## ログと測定値

CUDA/HIP 共通実装は、batch window 初期化時に attention または GDN の switch が有効なら stderr に `strata verify: batch rows in one launch: attention %s (STRATA_BATCH_ATTN_ROWS), GDN %s (STRATA_BATCH_GDN_GROUPS)%s` を出す。GDN の状態は `on` / `off` として出力され、両 switch が無効ならこの行は出ない。`STRATA_BATCH_ATTN_ROWS` が有効で KV streaming がある場合は、同じ行に `; the KV streams (--kv-resident), so attention keeps one launch per row` が付く。これは attention に関する注記で、GDN switch の値判定を変えない（`engine/src/core/verify.cpp:4661-4673`）。SYCL の batch window 初期化にはこの switch の on/off ログがない（`engine/sycl/src/core/verify.cpp:3317-3321`）。

CUDA/HIP の graph capture 失敗は `verify: begin batch capture failed`、`verify: end batch capture: ...`、commit graph の失敗は `verify: begin batch commit capture failed` 等のエラー文字列で `stage_batch` に返るが、これらは本変数専用の失敗ではない（`engine/src/core/verify.cpp:4677-4701, 4723-4726, 5311-5312`）。測定値はここでは記載しない。

`docs/BATCHING.md:704-719` は両 switch を「off by default」と説明する。一方、調査対象 commit では上記の Linux CUDA と一部 HIP 条件で Strata が unset の変数を `1` に設定するため、その記述は全構成には当てはまらない。現行動作はソースコードに基づき、条件ごとに記載した。

## 根拠

- `engine/src/core/verify.cpp:373-394, 1978-2007, 4661-4673, 4710-4773, 5302-5312`
- `engine/sycl/src/core/verify.cpp:1277-1305, 3317-3321, 3427-3463`
- `engine/src/core/arch_defaults.cpp:218-260, 302-310, 346-356, 433-442`
- `engine/include/strata/core/gfx11_extra.hpp:27-30, 116-132`
- `engine/src/program/generate.cpp:4287-4320, 4410-4414`
- `terminal/serve/server.py:4007-4028`
- `docs/BATCHING.md:704-719`
