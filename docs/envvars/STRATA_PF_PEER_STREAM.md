# `STRATA_PF_PEER_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

peer GPU を使う prompt prefill で、primary GPU が長い chunk 用の expert staging ring に流す非 resident expert のうち、一定割合を peer GPU 自身の ring に流して計算させる割合を指定する。CUDA/HIP 実装では P2P 転送経路と mapped host memory 経路のどちらでもこの peer ring を作る。SYCL 実装にも同名の読み取りがあるが、同実装の peer prefill 自体は P2P と MMQ prompt path が必要である。`engine/src/prefill/prefill.cpp:1351-1359,3437-3458`、`engine/sycl/src/prefill/prefill.cpp:683-692,2243-2249,2322-2348`

この値は `Prefill::set_peer` が peer prefill の compact buffer を初期化するときに読み、選ばれた expert の blob を peer 側の ring にコピーして peer GPU がその expert の routed rows を計算するように転送計画を変える。prompt の routed expert 選択自体を変える設定ではない。`engine/src/prefill/prefill.cpp:3333-3355,3437-3458,4688-4718,6063-6107`、`engine/sycl/src/prefill/prefill.cpp:2243-2249,2322-2348,3154-3187,4088-4118`

## 値と判定

両 backend とも環境変数の文字列を `std::atof` に渡す。明示的な空文字、数値に変換できない文字列、`0` は 0 になり無効。数値の先頭部分が変換され、後続文字列全体の検査はなく、明示的な clamp や有限値検査もない。したがって `0.4tail` は 0.4 として扱われ、負値や `NaN` は `> 0.0` 条件を通らず無効、正の数値は 1 を超えても有効になる。未設定時だけ backend/build 条件ごとの既定値を使う。`engine/src/prefill/prefill.cpp:3437-3444`、`engine/sycl/src/prefill/prefill.cpp:2322-2324`

| 条件（build / backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---:|---|---|
| CUDA/HIP `engine/src`、通常 build | `0.35` | 正数。例: `0.35`, `1`, `1.5` | `0`, `-0.1`, 空文字、`true`, `NaN` |
| CUDA/HIP `engine/src`、`STRATA_PF_OWN_ONLY` build かつ peer 対応 int8 layer がある | `0.0` | 正数を明示した場合。例: `0.35`, `1` | `0`, 負数、空文字、`true`, `NaN` |
| SYCL compact peer path | `0.35` | 正数。例: `0.35`, `1`, `1.5` | `0`, `-0.1`, 空文字、`true`, `NaN` |

`STRATA_PF_OWN_ONLY` build でも `any_peer_i8` が false なら CUDA/HIP の unset 既定値は `0.35`。設定値を 0..1 に制限するコードはない。各 chunk の expert 走査では pinned expert ごとに値を加算し、累積値が 1 以上ならその expert を peer ring に割り当てて 1 を引くため、1 を超える有限値では全ての対象 expert が選ばれる。`engine/src/prefill/prefill.cpp:3343-3355,3442-3458,4679-4710`、`engine/sycl/src/prefill/prefill.cpp:2322-2324,3154-3179`

## 有効になる条件

- prompt peer path が作られる必要がある。generate の `--peer-device` 設定から peer を開き、`--peer-prefill-rows` が 0 でないとき `set_peer` を呼ぶ。serve も valid peer と非 0 の peer prefill rows の場合に呼ぶ。既定 rows は `prefill_chunk * K / 2`。`engine/src/program/generate.cpp:1426-1433,4205-4209,10215-10219,13146-13153`
- compact buffer 経路であること。CUDA/HIP では `STRATA_PF_PEER_COMPACT=0` かつ P2P が使える場合、layer-sized buffer 経路に入り、この変数は読まれない。P2P がない CUDA/HIP peer 経路は compact を強制する。SYCL では compact が無効ならこの変数は読まれない。`engine/src/prefill/prefill.cpp:3412-3417,3437-3444`、`engine/sycl/src/prefill/prefill.cpp:2307-2312,2322-2324`
- 値が正でも peer 対応 layer と chunk 長が必要。CUDA/HIP は全 prompt layer が MMQ または peer int8 対応であること (`all_peer_layers`) と、初期化時の `m.T_max >= stream_all_min()` を満たさない場合に `ps_frac` を 0 に戻す。SYCL は MMQ fallback でないこと (`!mp.fallback`) と同じ chunk 上限条件を要求する。`engine/src/prefill/prefill.cpp:3343-3355,3444-3459`、`engine/sycl/src/prefill/prefill.cpp:2322-2348`
- 実際の chunk でも `T >= stream_all_min()`, `m.ring > STAGE`, `m.src != nullptr` が必要。短い chunk や staged path では peer-streamed flag が消去され、通常の primary 側処理に戻る。既定の長 prompt floor は SYCL で 1024 tokens。CUDA/HIP では `STRATA_PREFILL_STREAM_MIN` があれば `atoll` 値（0 以上を含む）を使い、なければ build/card 条件に応じた floor を使う。`engine/src/prefill/prefill.cpp:648-658`、`engine/sycl/src/prefill/prefill.cpp:211-217,3090-3092`
- CUDA/HIP の peer が無効なら未使用。peer layer に対応する prompt kernel が一つもなければ `set_peer` は失敗し、serve は理由を表示して prompt path を primary GPU に残す。SYCL `set_peer` は P2P がなければ失敗する。`engine/src/prefill/prefill.cpp:3333-3362`、`engine/sycl/src/prefill/prefill.cpp:2243-2249`、`engine/src/program/generate.cpp:13146-13153`

CLI による数値の上書きはなく、`--peer-device` と `--peer-prefill-rows` は機能経路と初期化上限を決める。peer の ring slot 数は別変数 `STRATA_PF_PEER_RING` が別途指定し、既定は 48。`engine/src/prefill/prefill.cpp:3444-3455`、`engine/sycl/src/prefill/prefill.cpp:2324-2345`

## 実行時の詳細

環境値は peer prefill buffer の初期化時に読み、`PeerPrefill::ps_frac` に保持する。request ごとの読み直しではない。CUDA/HIP では `set_peer` が呼ばれるたびに読み直し、SYCL も `set_peer` 内で読み直す。初期化後に環境を変えても、その `PeerPrefill` の割合には反映されない。`engine/src/prefill/prefill.cpp:3333-3340,3437-3444`、`engine/sycl/src/prefill/prefill.cpp:2243-2254,2322-2324`

長 prompt chunk の expert 列を layer と expert ID 順に走査する。resident expert と peer cache が保持する expert は除外され、source から安定した blob を得られる pinned expert だけが割合の累積対象となる。累積しきい値を越えた expert は peer 側 `pseq` と `ps_flag` に入り primary の staging sequence から外れる。peer ring の copy stream/queue が blob を slot に転送し、peer が計算した routed rows を primary 側の出力行に戻す。割合は概数の配分で、各 chunk の実際の選択数は対象 pinned expert 数に依存する。`engine/src/prefill/prefill.cpp:4670-4724,6063-6118,6725-6778`、`engine/sycl/src/prefill/prefill.cpp:3090-3092,3145-3194,4088-4118,4370-4395`

## ログと測定値

peer path の初期化が成功すると stderr に `strata prefill: peer GPU ...` が出て、compact かつ `ps_frac > 0` なら `streams N% of the primary's streamed experts through a N-slot ring` の部分が付く。割合は整数パーセントに丸めた表示で、値が 0 ならこの説明部分は出ない。`engine/src/prefill/prefill.cpp:3534-3545`、`engine/sycl/src/prefill/prefill.cpp:2380-2385`

peer ring buffer が確保できない場合、Strata は `prefill peer: the peer's buffers do not fit (raise --peer-reserve-mib or lower --peer-prefill-rows)` を返す。serve は `strata serve: <理由> - the prompt path stays on the primary GPU` と出して peer prompt path を使わない。SYCL の確保失敗は同じ buffer fit 理由を返す。`engine/src/prefill/prefill.cpp:3534-3538`、`engine/sycl/src/prefill/prefill.cpp:2379-2385`、`engine/src/program/generate.cpp:13146-13153`

Strata の `docs/DETAILS.md` にはこの変数の仕様記載は見つからなかった。`engine/src/prefill/prefill.cpp:3438-3441` のコメントには、MMQ 無し build の int8 peer layer で明示的に有効化した ring がある測定構成（2x V100-SXM2、IQ3_XXS、2K tokens 以上）で non-finite logits を出し、同じコメントの `STRATA_PF_PEER_STREAM=0` 条件では peer prompt path 無し build と bit-identical だったという報告がある。これはそのコメントの測定条件に限る記録であり、一般的な正確性保証や独立再測定としては扱えない。`engine/src/prefill/prefill.cpp:3438-3441`

## 根拠

- 実読取と CUDA/HIP の既定値・有効化判定: `engine/src/prefill/prefill.cpp:3333-3459`
- SYCL の peer 前提・読取・有効化判定: `engine/sycl/src/prefill/prefill.cpp:2243-2348`
- chunk ごとの割合配分と peer transfer plan: `engine/src/prefill/prefill.cpp:4670-4724`; `engine/sycl/src/prefill/prefill.cpp:3145-3194`
- 実行時の peer/primary への expert 割当: `engine/src/prefill/prefill.cpp:6063-6118,6725-6778`; `engine/sycl/src/prefill/prefill.cpp:4088-4118,4370-4395`
- CLI からの peer 設定呼び出し: `engine/src/program/generate.cpp:13146-13153`
