# `STRATA_PF_DMA_PAGEABLE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL prefill が expert blob を GPU へ送るとき、`ExpertSource::pinned()` が true とする host blob から直接コピーするかを制御する診断・互換用スイッチです。設定が有効なら、通常は USM host allocation かを確認してから行う直接 DMA を強制します。未設定時は host USM と確認できない blob を stager の pinned buffer にいったんコピーします。CUDA/HIP 側の prefill 実装にはこの変数の読み取り箇所がありません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

文字列全体の parse や大文字小文字変換はありません。判定は `getenv()` の結果が非 null で、`v[0] == '1'` かどうかだけです。判定結果は `dma_direct()` 内の関数ローカル `static const bool` に保存されます。したがって、最初に pinned source の expert を処理した後にプロセス環境を書き換えても再評価されません（それ以前に判定が初期化されていない場合は、最初の該当呼び出し時に読みます）。

## 有効になる条件

- SYCL backend の prefill が実行されること。
- 対象 expert について `ExpertSource::pinned(layer, expert)` が true であること。値を有効にしても、unpinned expert は直接 DMA の対象になりません。
- prefill の該当 copy 経路まで到達すること。キャッシュ上ですでに resident な expert や、別 GPU の peer が担当する expert はその経路を通りません。

このスイッチが無効のときは、`dma_direct()` が blob の 2 MiB bucket の両端と blob 自身に対して `sycl::get_pointer_type(..., context) == sycl::usm::alloc::host` を確認します。3箇所すべてが host USM の場合だけ直接コピーし、それ以外は stager 経由になります。bucket ごとの結果はスレッドローカル map に保存されます。有効時はこの USM 判定を飛ばし、pinned 判定を満たした blob を直接コピー側へ送ります。

## 実行時の詳細

`STRATA_PF_DMA_PAGEABLE` は `sycl/src/prefill/prefill.cpp` の `dma_direct()` だけで読み取られます。大きな streamed-prefill 経路と、layer ごとに expert を段階転送する経路の双方がこの関数を使います。直接コピー側は copy queue から `m.stage_dev[slot]` へ blob を転送し、`stats_.experts_dma` を増やします。stager 側は stager thread が pinned buffer へコピーした後、その buffer から DMA します。

この変数を有効にすると、SYCL port で従来の直接コピーを復元します。`docs/INTEL.md` は、Arc A750 で pageable memory から Level Zero の staging 経由で直接コピーした際に prompt が停止する事例があったため、通常は host USM と確認できる expert だけを直接転送し、それ以外を stager 経由にしたと説明しています。同資料は `STRATA_PF_DMA_PAGEABLE=1` で旧方式に戻ると記載しています。この資料中の停止回数、速度、token 同一性は記載された A750/B70 と個別プロンプトでの報告値であり、ここで再測定した結果ではありません。

## 根拠

- `sycl/src/prefill/prefill.cpp:111-135`: SYCL の pageable/pinned 前提、変数の読み取り、USM host 判定と bucket cache。
- `sycl/src/prefill/prefill.cpp:2794-2822`: streamed-prefill 経路の blob 選択と direct/stager の振り分け。
- `sycl/src/prefill/prefill.cpp:4084-4145`: layer 単位の経路での direct/stager 判定、GPU へのコピー。
- `sycl/src/core/expert_source.cpp:2391-2400,3621-3625`: File/Arena expert source における `pinned()` 判定。
- `docs/INTEL.md:780-795`: A750 の停止事例、変更後の確認と、この変数で旧方式に戻るという説明。測定条件は同資料の記載に限定。
