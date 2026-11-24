# `STRATA_INK_SPEC_PLAIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA Inkling-2 の DSpark speculative beam tree で、1〜2 ノードの小さい tree を候補に含めるときの評価係数を設定する。係数が正なら `draft_beam_tree` は動的 tree サイズ選択で 1・2 ノード候補を調べ、その候補の rate に係数を乗じる。0 以下ならこの 2 候補を除外する。tree の後段は target 側の argmax をたどるため、この値が直接 token 選択規則を変更する処理ではなく、ドラフト tree の大きさを選ぶ基準を変える（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1080`、`engine/src/inkling2/cuda/ink_dspark.cuh:1754-1778`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:1083-1101`）。

Strata ソース中でこの名前を読むのは `InkCudaBackend::init` のみ。CUDA Inkling-2 バックエンドで `std::getenv` から値を読み、`BackendOpts::spec_plain` と組み合わせて `spec_cfg_.plain` に保存する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125`）。HIP、Metal、SYCL、CPU の同名環境変数読み取りは確認できない。

## 値と判定

環境変数は設定されている場合に `std::atof` で `float` に変換する。未設定なら構造体の初期値 `0.0f`。空文字や数値として変換できない文字列（`true` / `false` など）は `atof` の結果が 0 になる。先頭の空白は数値変換時に読み飛ばされるが、数値文字列全体の厳密な検証やエラー報告はなく、`atof` が認識する数値の後ろに文字列がある場合も変換された数値部分が使われる。大文字小文字を比較する分岐はなく、真偽値文字列としての特別扱いもない。変換後の値に clamp はない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:118-123,1205-1206`）。

| 条件 | unset | 有効になる値（例） | 小 tree 候補に無効な値（例） |
|---|---|---|---|
| CUDA Inkling-2 backend、CLI `--draft-plain` が未指定または負値 | `0.0` | `0.1`, `1`, `2.5`, ` 1`, `1junk`（先頭空白を除き数値 prefix は `atof` で変換） | 空文字、`abc`, `true`, `false`, `0`, `-1`, `0anything` は 0 以下となる |
| 同 backend、CLI `--draft-plain` が 0 以上 | 環境変数値より CLI 値を優先 | `--draft-plain 0.5`, `--draft-plain 1` | `--draft-plain 0` は CLI が環境変数を上書きして小 tree 候補を無効化 |

CLI 値も `std::atof` で作られ、backend init では `opts.spec_plain >= 0.0` のときに環境変数由来の値を上書きする。したがって CLI の 0 は明示的な override、負数は override せず環境変数値を残す。CLI も環境変数も未設定のときは `spec_plain = -1.0` と `spec_cfg_.plain = 0.0f` が維持される（`engine/src/inkling2/ink_main.cpp:904-905`、`engine/src/inkling2/ink_backend.h:39`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:120-123,1205-1206`）。

## 有効になる条件

- CUDA Inkling-2 backend の初期化が必要。この環境変数の読み取り実装は `engine/src/inkling2/cuda/ink_cuda_backend.cu` に限られる（同ファイル `:117-125`）。
- backend init 時に `--draft-plain` の値が負でなければ CLI が優先する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:120-123`）。
- 実際の小 tree サイズ評価には `draft_beam_tree` に渡される `adaptive_moe_ratio > 0` も必要。現在の呼び出しでは `spec_cfg_.cost` が `adaptive_moe_ratio` であり、`--draft-cost` は正値のときだけ環境変数値を上書きする。cost が 0 以下の場合、動的 sizing ブロック自体を通らず `want = min(max_nodes, cnt)` が使われる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:119-123,1073-1077`、`engine/src/inkling2/cuda/ink_dspark.cuh:1754-1779`）。
- DSpark が有効かつ ready であることが必要。CUDA backend は `opts.enable_dspark` と model manifest の DSpark の両方が成立し、layer-split でない場合に drafter を初期化する。初期化時の VRAM 不足では `[InkCUDA] DSpark drafter turned off: not enough free GPU memory for it (%s)` を stderr に出して無効化する（`engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352`）。
- CUDA greedy tree step は slot 0、DSpark ready、layer-split ではないこと、context headroom などを要する。serve ではさらに DSpark 使用中・active request が 1 件・prefill 完了・生成残りが 2 token 以上・greedy sampling・penalty なしなどの条件がある（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1065-1067`、`engine/src/inkling2/ink_serve.h:876-890`）。`--draft off` なら serve の DSpark 使用は無効（`engine/src/inkling2/ink_serve.h:507`）。
- server の `STRATA_INK_SPEC=block` は greedy request を block-8 経路に切り替えるため、この tree sizing 経路では値を使わない（`engine/src/inkling2/ink_serve.h:508-510,882-884`）。`STRATA_INK_SPEC=adapt` や `--draft-adapt` は測定された gain に応じて speculative step を一時停止する別の条件であり、停止中はこの値による tree 選択も行われない（`engine/src/inkling2/ink_serve.h:511-525,876-880`）。
- 単独 CLI の直接生成ループは通常の `forward_batch` を呼び、speculative tree step の呼び出しがない。この変数が効くのは tree step を呼ぶ経路（server の greedy fast path、および DSpark 有効かつ単一 slot の bench path）に限られる（`engine/src/inkling2/ink_main.cpp:196-218,1086-1113`）。

## 実行時の詳細

`InkCudaBackend::init` が呼ばれるたびに環境変数を読み、CLI override と合わせて backend メンバー `spec_cfg_.plain` に格納する。各 speculative request/step で環境を再読込したり、環境値を static cache したりはしない。プロセス中に環境を変更しても保存済み設定は変わらず、再初期化されればその時点の値が読まれる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1205-1206`）。

Greedy tree step は `spec_cfg_.cost` と `spec_cfg_.plain` を `draft_beam_tree` に渡す。dynamic sizing はノード数候補 `{1,2,3,4,5,6,8,10,12,16}` から、上限 `max_nodes`（最大 12）および候補 pool 数を超えないものを評価する。`plain_margin <= 0` なら 1・2 ノードを飛ばし、正なら各小 tree の rate を `plain_margin` 倍する。最大 rate の候補を `want` にし、pool の上位候補を親 node を保ちながら tree に残す（`engine/src/inkling2/cuda/ink_dspark.cuh:1696-1701,1754-1778,1781-1807`）。

選ばれた tree は target の tree verify に進み、各 node の target argmax を使って一致する子へ進みながら token を出力する。従ってこの変数は draft tree の node count 選択に作用し、target の greedy argmax による検証を省略するものではない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1080,1083-1101`）。

## ログと測定値

この変数の値・無効値・小 tree 選択についての専用ログ、警告、エラーはない。backend init で変換失敗を報告せず、通常の `[SPEC-STATS]` ログは別の `STRATA_INK_SPEC_LOG` が設定されている場合に限り 200 speculative steps ごとに stderr に出る（`engine/src/inkling2/cuda/ink_cuda_backend.cu:125,1115-1119`）。DSpark 自体の VRAM 不足ログは「有効になる条件」に記載した。

この変数による性能測定値は、調査対象ソースと `docs/DETAILS.md` に確認できなかった。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,343-352,1057-1080,1083-1101,1115-1119,1205-1206`
- `engine/src/inkling2/cuda/ink_dspark.cuh:1696-1701,1754-1778,1781-1807`
- `engine/src/inkling2/ink_backend.h:36-40`
- `engine/src/inkling2/ink_main.cpp:196-218,904-905,1086-1113`
- `engine/src/inkling2/ink_serve.h:507-525,876-890`
