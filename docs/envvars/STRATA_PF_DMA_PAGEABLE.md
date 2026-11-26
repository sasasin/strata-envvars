# `STRATA_PF_DMA_PAGEABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL prefill が expert blob を host から device へ転送するとき、`ExpertSource::pinned()` が true と判定した blob を直接コピーの対象にします。既定では、そのポインタが SYCL の host USM であることを確認し、そうでなければ stager の host buffer にコピーしてから device へ送ります。この変数を有効にすると、その USM 判定を飛ばして元の blob から直接コピーします。したがって「pinned」という Strata の source 判定だけでなく、ページ可能なメモリからの直接コピーも許可する設定です。対象は `engine/sycl/src/prefill/prefill.cpp` の `dma_direct()` です（同ファイル:151-168）。

## 値と判定

`dma_direct()` が `src->pinned(layer, expert)` を確認した後、関数内 `static const` の初期化処理で `std::getenv` を一度呼び、値が存在し、先頭 byte が文字 `'1'` なら有効とします。文字列全体の parse や数値変換はしません。空文字は無効、`1anything` は有効、`0`・`0anything`・`true`・`True`・先頭に空白のある ` 1` は無効です。unset も無効です（同ファイル:151-155）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL prefill で `src->pinned()` が true の blob | USM 判定を行う | `1`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1` |
| `src->pinned()` が false | 環境変数を読む前に直接コピー対象外 | 該当なし | 設定値にかかわらず直接コピー対象外 |

## 有効になる条件

- この実装が使われる SYCL prefill 経路であること。CUDA/HIP 実装に同じ名前の読み取りはありません（同ファイル:151-153）。
- 対象 expert が host-resident cache や peer 側で処理されず、prefill の expert staging 対象になること（同ファイル:3158-3186、4605-4624）。
- `ExpertSource::pinned(layer, expert)` が true であること。この判定は `ArenaExpertSource` では expert の範囲と `pinned_bytes_`、`FileExpertSource` では complement の状態・範囲等、`GgufExpertSource` では mirror pointer の有無で決まります（`engine/sycl/src/core/expert_source.cpp:2402-2410`, `engine/sycl/src/core/expert_source.cpp:3621-3625`, `engine/sycl/src/core/gguf_expert_source.cpp:210-213`）。
- stream-all 経路で `gsrc != nullptr` の場合は、expert を GGUF から stager thread が読む job にするため `dma_direct()` を呼びません。`gsrc` は `STRATA_GGUF_PLAN_READ=1` のとき null にされます。したがって `STRATA_PF_DMA_PAGEABLE=1` が direct 判定を変えるのは、その GGUF job 経路を通らず、かつ `pinned()` が true の場合です（同ファイル:3090、3143-3145、3163-3184）。
- `--stream-experts` は GGUF source や USM mirror を使う経路に関係しますが、この環境変数に対する優先設定ではありません。非 stream-all 経路では stager job を作る前に `dma_direct()` を呼びます。通常はそこで実際の host USM かどうかも検査します（同ファイル:144-168、4605-4624）。

## 実行時の詳細

未設定または先頭 byte が `'1'` でない場合、`blob` が null なら直接コピーを拒否します。そうでなければ、ポインタを含む 2 MiB bucket の先頭・末尾と blob 自体を `sycl::get_pointer_type` で調べ、すべて `sycl::usm::alloc::host` のときだけ直接コピーを許可します。bucket ごとの判定結果はスレッドローカル map に保存されます（同ファイル:155-167）。

先頭 byte が `'1'` の場合は `blob == nullptr` の確認より先に直接コピーを許可します。ただし `dma_direct()` を呼ぶ stream-all 経路ではその前に null blob をエラーにし、通常の stage 経路でも direct 判定後に blob が null なら `prefill: expert source has no blob` を返します。stream-all の GGUF job 経路では `dma_direct()` 自体を通らず、stager が読む経路になります（同ファイル:3163-3184、4669-4674）。この設定は source の存在確認を取り除きません。

環境値はプロセス起動時ではなく、`dma_direct()` が初めて `pinned()` true の expert で呼ばれたときに関数内 static として初期化されます。それ以降の環境変更はこのプロセス内の判定に反映されません。`pinned()` false の呼び出しは static 初期化より前に戻るため、その時点ではまだ読み取りません（同ファイル:151-154）。

direct が false の expert は stager job に加えられ、stager の buffer から device へコピーします。direct が true の expert は source blob から device へコピーし、`experts_dma` 統計を増やします。どちらの経路もその後は prefill の expert staging/routing に進みます（同ファイル:3181-3194、3206-3231、4610-4624、4669-4689）。

## ログと測定値

この変数の読み取りや有効化を示す専用ログはありません。SYCL のコピーで例外が発生した場合、該当する catch 経路は例外文と `Exception caught at file:...` を stderr に出し、`exit(1)` します（同ファイル:3235-3239、4692-4696）。変数固有の測定値は、参照した Strata の資料に条件付きで記載されていません。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:144-168` — 対象関数、値判定、USM fallback と bucket cache。
- `engine/sycl/src/prefill/prefill.cpp:3158-3195`, `engine/sycl/src/prefill/prefill.cpp:4603-4626`, `engine/sycl/src/prefill/prefill.cpp:4660-4689` — staging 経路からの利用とコピー元。
- `engine/sycl/src/core/expert_source.cpp:2402-2410`, `engine/sycl/src/core/expert_source.cpp:3621-3625`, `engine/sycl/src/core/gguf_expert_source.cpp:210-213` — source ごとの `pinned()` 判定。
- `engine/sycl/src/prefill/prefill.cpp:3235-3239`, `engine/sycl/src/prefill/prefill.cpp:4692-4696` — コピー時の SYCL 例外経路。
