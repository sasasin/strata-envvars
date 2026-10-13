# `STRATA_KV_PREFETCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

prefill 中、次の attention layer が使う KV prefix を専用の非同期 stream/queue で先に staging pool へ転送し、現在の layer の計算と重ねます。対象は QSA state の KV が `kv_mode == 1` の経路です。この mode では host copy が正本で、GPU 上には一部の slot が置かれます。VRAM 内だけで完結する mode 0 や MTP 用 ring の mode 2 では、この prefetch は行われません（`include/strata/core/layer.hpp:233-237`）。

この変数は KV streaming 自体を有効にする設定ではなく、既に KV streaming になっている prefill の prefix staging の順序を変える opt-in です。追加の KV staging pool は確保せず、既存の pool を再利用します。

## 値と判定

CUDA/HIP 共通側と SYCL 側の両実装で、`std::getenv()` の戻り値に `std::atoi(e) != 0` を適用します。文字列全体の検証はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | `atoi("") == 0` のため無効 |
| 数字として先頭から変換した値が 0 | 無効。例: `0`, `0tail`, `true`, `junk`, `0.5` |
| 数字として先頭から変換した値が 0 以外 | 有効。例: `1`, `-1`, `2tail`, `1.0` |

`atoi` は先頭空白と符号の後の十進数字列を変換し、数字列の後ろは判定に使いません。したがって `1anything` も有効ですが、`true` は有効になりません。数値として妥当か、変換の終端まで読めたかを別途確認する処理や、値の clamp はありません。

判定は `Prefill::run_impl()` 内の関数ローカル `static const bool` で一度だけ行います。プロセス内で最初にこの関数が呼ばれた時点の値が以後の呼び出しにも使われるため、その後の環境変更は反映されません（`src/prefill/prefill.cpp:2040-2059`、`sycl/src/prefill/prefill.cpp:2101-2122`）。

## 有効になる条件

値が非ゼロでも、次の条件に合う区間だけで転送を行います。

- prefill の現在位置 `p0` が 0 より大きい。初期 prefix がない `p0 == 0` の呼び出しでは何もしません。
- 対象 layer が QSA で、対応する state の `kv_mode == 1` である。
- prefill の当該 stage 範囲 `[LB, LE)` に次の該当 layer がある。

候補 layer は範囲内から順に探され、mode 1 以外の QSA layer は飛ばされます。layer が見つからなければ prefetch は投入されません。各 chunk で staging pool は一つだけなので、未消費の prefetch がある間は次の prefetch を開始しません（`src/prefill/prefill.cpp:2241-2271`、SYCL: `sycl/src/prefill/prefill.cpp:2401-2459`）。

## 実行時の詳細

有効時は、CUDA 側で非ブロッキング stream と `kv_released` / `kv_ready` event を、SYCL 側で別 queue と対応する event を必要に応じて作成します。確保に失敗したときは `prefill: KV prefetch stream/events` をエラーにして `run_impl()` が失敗します（CUDA: `src/prefill/prefill.cpp:2060-2067`、SYCL: `sycl/src/prefill/prefill.cpp:2123-2138`）。

chunk の開始時に次の該当 layer を探して先行転送を投入し、その後は QSA layer の attention 計算を終えた箇所から次の候補を予約します。転送対象は host copy にある `[0, p0)` の prefix で、ページ数は `(p0 + page_size - 1) / page_size` です。再利用する pool を前の attention reader が使い終わるよう compute stream 上に release event を置いてから別 stream/queue で転送し、ready event を記録します。対象 layer の通常の prefix staging 箇所では、その ready event を待ってから pool を読みます。予約がない layer は従来どおり compute stream/queue 上で `kv_stage_from_host()` を実行します（CUDA: `src/prefill/prefill.cpp:2244-2269,2647-2660,2853-2858`、SYCL: `sycl/src/prefill/prefill.cpp:2405-2458,2930-2944,3193-3198`）。

つまり転送そのものを省く機能ではなく、次の prefix 転送を現在の層の計算中に進めます。chunk の新しい KV 行の書き込み方法はこの変数では変更しません。早期 return 時には RAII cleanup が転送 queue を drain し、正常終了時にも stream/queue を待ちます。relayout と Prefill 解放時も既存 queue の処理完了を待ってから片付けます（CUDA: `src/prefill/prefill.cpp:2068-2072,915-932,1313-1315,4102-4108`、SYCL: `sycl/src/prefill/prefill.cpp:2140-2145,791-812,1257-1260,4592-4612`）。

有効で prefill が正常終了すると stderr に `strata KV prefetch: %lld layer prefixes, single existing staging pool` が出ます。件数はその `run_impl()` 呼び出しで投入した prefix 数で、0 件の場合も有効なら表示されます。CUDA 側は queue 同期失敗時に `prefill: KV prefetch stream: <CUDA error>`、投入・待機の失敗時にそれぞれ `prefill: releasing KV staging pool`、`prefill: enqueueing KV prefetch`、`prefill: waiting for KV prefetch` を返します。SYCL 版も同じエラー文言を設定する箇所がありますが、移植層の event/error 判定コードを含み、資料上もこの経路の backend 検証範囲は限定されています。SYCL の実行時の非同期エラー挙動を CUDA と同一とは断定しません。

## 資料との照合・制限

`docs/KV_PREFETCH.md:5-18` は、host RAM にある長い KV prefix の転送を次 layer の計算と重ね、既存 pool を再利用する opt-in と説明しています。コード上の既定無効、event による pool 再利用保護、早期 return/relayout/destruction 時の drain と一致します。同資料の性能表は、過去の独立 prototype（v0.1.38 ベース）の測定であり、同資料自身が現在の pure-upstream port の speedup を測った値ではないと明記しています。そのため本調査では現行 HEAD の性能向上や精度・token 同一性を主張しません。資料は HIP と他 GPU の検証も未完了としています（同 `:29-32,34-56`）。

## 根拠

- 値の読み取りと既定値、CUDA/HIP 共通側: `src/prefill/prefill.cpp:2040-2067`。
- SYCL 側の読み取りと queue/event 初期化: `sycl/src/prefill/prefill.cpp:2101-2145`。
- mode 1 の意味: `include/strata/core/layer.hpp:233-237`。
- 候補検索、転送、consumer の待機: `src/prefill/prefill.cpp:2241-2271,2647-2660,2853-2858`、`sycl/src/prefill/prefill.cpp:2401-2459,2930-2944,3193-3198`。
- 完了ログ、後始末、資料上の検証範囲: `src/prefill/prefill.cpp:915-932,1313-1315,4098-4108`、`sycl/src/prefill/prefill.cpp:791-812,1257-1260,4592-4612`、`docs/KV_PREFETCH.md:15-18,29-56`。
