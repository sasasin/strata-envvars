# `STRATA_FUSE_WAIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MoE の部分常駐経路で、ホスト側の flag を待つ GPU 処理と、その後の mapped memory の読み取り・コピーを同じ kernel launch にまとめるかを制御する。CUDA では GPU が作成した plan の待ち（`wait_copy_i32_from_mapped`）と CPU rows の待ち・コピー（`copy_rows_from_mapped_after`）を別々に制御する。HIP では同じ有効判定を両方に使う。いずれも待ち条件やコピー対象のデータ自体を変える設定ではなく、launch をまとめる経路を選ぶ（`engine/src/core/verify.cpp:468-471,491-522,2847-2857,2863-2876,2913-2930`）。

## 値と判定

各読み取りは `std::getenv` と `std::atoi`。数値文字列全体の検証はせず、`atoi` が読める先頭の整数を使うため、先頭空白・符号を許し、数字の後ろは無視する。空文字や数字で始まらない値は `0`。小数は整数部分まで（例 `1.5` は `1`）。

| build / 読み取り先 | unset | `atoi` の結果と有効値 | 明示的な無効値など |
| --- | --- | --- | --- |
| HIP: plan と rows | `-1` の sentinel から GPU 判定へ。gfx12 なら ON、それ以外または device 情報取得失敗なら OFF | `0` 以外は ON（例 `1`, `2`, `-2`） | `0` は OFF。空文字、`true`、`0anything` も `0` となり OFF |
| CUDA: plan wait | `-1` の sentinel から sm_75 判定へ。compute capability 7.5 なら ON、それ以外なら OFF | `1` または `2` だけ ON | `0` と `3` 以上は OFF。負数は sentinel と同じく hardware 判定へ |
| CUDA: CPU rows wait | 常に OFF | `atoi` がちょうど `1` のときだけ ON | `0`, `2`, `3`, 負数、空文字、`true` は OFF |

このため CUDA の `STRATA_FUSE_WAIT=2` は plan wait だけを融合し、`=1` は plan wait と rows wait の両方を融合する。HIP では `=2` も両方を有効にする。たとえば `1anything` は両 build で `atoi` 結果が `1` だが、`2anything` は CUDA では plan のみ、HIP では両方に有効（`engine/src/core/verify.cpp:491-522`）。

CUDA sm_60 の既定値設定が適用される場合、未設定の変数は `STRATA_FUSE_WAIT=2` にされる。ユーザーが空文字を含む何らかの値を設定していれば保持される（`engine/src/core/nv_defaults.cpp:164-175,222-237`）。

## 有効になる条件

- CUDA / HIP の GPU engine 内の `Verifier` 経路が対象。HIP 分岐は `STRATA_USE_HIP` で選ばれる（`engine/src/core/verify.cpp:491-512`、`engine/cmake/hip_backend.cmake:109`）。
- HIP で unset の hardware 既定 ON は、`cudaGetDevice` と `cudaGetDeviceProperties` が成功し、現在 device の `gcnArchName` が `gfx_arch_is_gfx12` に一致する場合だけ。device 番号の取得失敗・範囲外・property 取得失敗では OFF（`engine/src/core/verify.cpp:498-505`）。
- CUDA で unset の plan 既定 ON は、`device_is_sm75()` が true の場合だけ。これは compute capability を取得でき、`strata::sm75_default(major, minor)` が true、すなわち sm_75 series が有効な場合（`engine/src/core/verify.cpp:473-488,507-513`）。rows の unset 既定は常に OFF。
- CUDA の起動時既定値 `=2` は、全 visible CUDA device が同じ compute capability で、能力値が 6.0 のときにだけ sm_60 table から候補になる。`STRATA_SM60_PERF` の先頭文字が `0` なら table は適用されない。環境にすでに `STRATA_FUSE_WAIT` があれば、その値が優先される（`engine/src/program/generate.cpp:4421-4448`, `engine/src/core/nv_defaults.cpp:15-18,164-175,222-237`）。
- Plan wait の融合箇所は host pool から plan を受け取る `!device_plan_` 経路で、`fuse_wait_on()` が true、profiling が OFF、`m_bal_ == nullptr` の場合。device plan 側は別の wait/copy 経路を使う（`engine/src/core/verify.cpp:2863-2876`）。
- CPU rows の融合にはさらに decode batch（`dec_batch`）が必要。remote helper (`remote_opt_`) がないこと、`m_bal_ == nullptr` も必要。条件を満たさなければ通常の flag wait 後に mapped rows をコピーする（`engine/src/core/verify.cpp:2847-2857,2913-2930`）。
- 全 expert が VRAM にある all-resident 経路や device-hits plan の経路では、plan wait の融合分岐を通らない。device-hits の CPU rows は条件が整えば rows 側の融合候補になる（`engine/src/core/verify.cpp:2828-2857`）。CLI 引数でこの環境変数を上書きする処理は確認できない。

## 実行時の詳細

`fuse_wait_on()` と `fuse_rows_on()` はそれぞれ関数内 `static` に判定を保存する。unset の hardware 既定も最初の呼び出し時に判定され、以降プロセス内で環境変数を変更しても再評価されない。通常は engine 起動時に CUDA sm_60 table が switch を設定してから読み取りに進む（`engine/src/core/verify.cpp:491-522`, `engine/src/program/generate.cpp:4421-4449`）。

有効な plan wait は、flag を待ってから plan 配列を mapped host memory から読む処理を一つの kernel launch にする。rows wait は flag を待ちながら対象 CPU rows を mapped memory からコピーする kernel に置き換える。OFF または適用条件外なら、従来どおり wait kernel と copy kernel を別に呼ぶ。条件を満たす fusion でも、flag が所定値に達するまで GPU kernel 内で待機するため、環境変数自体が timeout や失敗時の別処理を導入するわけではない（`engine/src/core/verify.cpp:2847-2857,2868-2876,2913-2930`; kernel 実装 `engine/src/kernels/cuda/verify_kernels.cu:1907-1925`, `engine/src/kernels/cuda/elementwise.cu:289-298`）。

## ログと測定値

rows 経路の分岐は `experts layer: cpu rows via %ld (1 = fused wait+copy, 0 = wait then copy), hits in combine=%ld` を dispatch stats の note として記録する。`STRATA_DISPATCH_STATS` が未設定または先頭文字が `0` 以外なら記録され、`STRATA_DISPATCH_REPORT` の JSON report、または CLI `--stats` の stdout `dispatch` report で確認できる。note の `%ld` は rows fusion の条件が成立したとき `1`。plan wait 専用の有効状態を示す同等の note はこの分岐にはない（`engine/src/core/verify.cpp:2932-2937`; `engine/include/strata/core/dispatch_stats.hpp:9-11,59-68,107-119,145-152`）。

CUDA sm_60 で起動時 defaults が環境に値を追加した場合は、`stderr` に `strata: sm_60 (Pascal): ... speed switches on by default ...` の行が出て、追加された switch 名の一覧に `FUSE_WAIT` が含まれる（`engine/src/core/nv_defaults.cpp:240-255`）。

実装コメントは、gfx1201 graph で依存 kernel が約 2.4 µs という記載を gfx12 の測定に基づく既定化理由として挙げる。また CUDA Turing の plan wait 既定 `2` について RTX 2080 Ti / Flash-Next Q2_0 / 2 runs で decode +0.6〜+1.4%、rows 版は同条件で -1.5% と記している。いずれもソースコメント上の測定値であり、一般的な性能保証ではない（`engine/src/core/verify.cpp:468-510`）。

## 根拠

- `engine/src/core/verify.cpp:468-522` — 変数の全読み取り箇所、backend ごとの parse、hardware fallback。
- `engine/src/core/verify.cpp:2827-2876,2908-2937` — MoE 経路、fusion 適用条件、rows 状態ログ。
- `engine/src/kernels/cuda/verify_kernels.cu:1907-1925` — plan wait と copy を統合する kernel。
- `engine/src/kernels/cuda/elementwise.cu:289-298` — flag wait と rows copy を統合する kernel。
- `engine/src/core/nv_defaults.cpp:15-18,164-175,222-255` — sm_60 既定値の候補、ユーザー設定の優先、stderr 出力。
- `engine/src/program/generate.cpp:4421-4449` — CUDA の device 構成確認と起動時 defaults 呼び出し。
- `engine/include/strata/core/sm75_series.hpp:37` — sm_75 hardware 既定 predicate。
- `engine/include/strata/core/dispatch_stats.hpp:9-11,59-68,107-119,145-152` — rows note の有効条件と report 出力先。
- `engine/cmake/hip_backend.cmake:109` — HIP backend build macro。
- `docs/DETAILS.md:1336-1343,1478-1488` — Turing opt-in と sm_60 既定値についての資料。現行実装の判定は上記ソースを根拠とした。
