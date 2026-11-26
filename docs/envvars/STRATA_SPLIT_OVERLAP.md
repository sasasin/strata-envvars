# `STRATA_SPLIT_OVERLAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

serve の複数 GPU layer split で、ある stage の verify window が次 stage へ hidden state を渡すとき、ホスト側で stage 間を同期してから次の graph を起動する順序を、GPU 上の ready flag を介した重ね合わせに切り替える。設定は任意で、通常は無効。`engine/src/program/generate.cpp` が値を読み、各 `Verifier` に hand-off flag を設定する。後続 stage の graph は前 stage の hand-off を GPU 上で待つため、window の計算内容そのものを変える分岐ではない（`engine/src/program/generate.cpp:13351-13387`、`engine/include/strata/core/verify.hpp:215-225`、`engine/src/core/verify.cpp:1642-1651,2998-3013`）。

この読み取りは `n_stages > 1` の serve 初期化経路にあり、生成 CLI や単一 GPU 実行には適用されない。読み取り箇所には OS 別の分岐がない。CUDA API を使う GPU 実行経路で、資料は NVIDIA と AMD の測定を掲載している（`engine/src/program/generate.cpp:13247-13256,13351-13362`、Strata checkout 内 `docs/MULTI_GPU.md:155,172-178`）。

## 値と判定

`std::getenv` で取得した文字列を `std::atoi` に渡し、その整数が 0 以外かを判定する。文字列全体の検証やエラー報告はなく、`atoi` が先頭から整数として変換できる範囲だけを使う。空文字、数値変換できない文字列、先頭の数値部分が 0 の文字列は無効。負の非ゼロ値も有効になる。整数範囲を超える入力の結果は `atoi` の範囲外動作に依存するため、設定値としては定義できない（`engine/src/program/generate.cpp:13354-13357`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| serve の複数 stage layer split 初期化時 | `overlap_asked=false` | `1`, `2`, `-1`, `1suffix`（`atoi` の結果が非ゼロ） | 空文字、`0`, `0suffix`, `true`, `false` |

この変数に CLI 引数や他の設定値から値を上書きする処理はない。明示的な設定があっても、下記の適用条件を満たさなければ実動作は有効にならない。値はこの初期化経路で一度読み、リクエストごとには再読しない（`engine/src/program/generate.cpp:13354-13362`）。

## 有効になる条件

- `--serve` による server 実行で、2 stage 以上の layer split が組まれること。読み取り自体がその初期化ブロック内にある（`engine/src/program/generate.cpp:13247-13256,13354-13359`）。
- hand-off 先が別 GPU であること。`--split-device 0` のように同じ GPU 上へ stage を置く場合は overlap しない。実行時の chain 判定も、次 stage の device が異なり、次 stage が PLE stage でないことを要求する（`engine/src/program/generate.cpp:13351-13359`、`engine/src/core/verify.cpp:3705-3708`）。
- `o.pipeline_windows == 0` であること。正の値ではこの設定を無効にし、`--pipeline-windows` 側のループに任せる。自動設定でも `o.pipeline_windows` が正になる場合があり、HIP gfx12 の複数 stage split などでは既定で pipeline windows が選ばれ得る。`--pipeline-windows 0` は明示的に off にする設定（`engine/src/program/generate.cpp:6532-6537,6560-6582,13358-13362`）。
- バッチ window は ready flag の wait/publish 条件 `!batch_rec_` を通らず、シリアル順で処理される（`engine/src/core/verify.cpp:1645-1651,3003-3013`）。
- flag 用の mapped host memory の確保に成功すること。確保または device pointer 取得に失敗すると stderr に `strata serve: the layer-split hand-off flag allocation failed` を出して初期化を終了する（`engine/src/program/generate.cpp:13363-13372`）。

## 実行時の詳細

有効時、各 stage 間に mapped ready flag を割り当て、Verifier に hand-off の入力・出力 flag を設定する。前 stage の GPU は residual 等の hand-off payload を書いた後に ready word を上げる。後 stage の graph は hand-off 入力を読む前に GPU 上で ready word を待つ。ホスト thread は stage 間の同期を挟まず次 stage の `run` へ進み、chain 完了後に各 stream を同期する（`engine/src/program/generate.cpp:13363-13387`、`engine/include/strata/kernels/verify_kernels.hpp:109-118`、`engine/src/core/verify.cpp:1642-1651,3003-3013,3840-3846,4123-4139`）。

flag の GPU wait は別変数 `STRATA_SPLIT_WAIT_MS` で制限され、既定は 30000 ms、0 は無期限。wait が時間切れになると GPU 側の error word が立ち、Verifier は `verify: layer split: the hand-off into layer ... did not arrive within ... ms (STRATA_SPLIT_WAIT_MS); the window was not used. STRATA_SPLIT_OVERLAP=0 runs the serial order` をエラーとして返す（`engine/src/core/verify.cpp:658-664,3696-3702`）。serve の decode window 呼び出し元は `ERR <理由>` を stdout に出して終了コード 1 で戻る（`engine/src/program/generate.cpp:22990-22994`）。

## ログと測定値

`overlap_asked` が真で `--pipeline-windows` の実効値が正なら、stderr に `strata serve: STRATA_SPLIT_OVERLAP is off beside --pipeline-windows %d (that loop overlaps the stages itself)` を出す。overlap が有効な layer split の起動行には ` (overlapped: STRATA_SPLIT_OVERLAP=1)` が付く。無効値や未設定ではこの追記はない（`engine/src/program/generate.cpp:13358-13362,13423-13429`）。

`docs/MULTI_GPU.md` は、2x RX 7900 XTX・Swift 1.5 IQ3_XXS・128K・中央値8回で code decode 53→70.1 tok/s、prose 45→55.9 tok/s、2x RTX A4000・IQ3_XXS では story +0.3%、code +2.1%、facts -0.3%（同資料の記述ではノイズ範囲）と報告している。これは文書に記載された測定値であり、今回の調査で再測定したものではない（`docs/MULTI_GPU.md:286-300`）。

## 根拠

- `engine/src/program/generate.cpp:13247-13256` — layer split の stage 数と serve 経路。
- `engine/src/program/generate.cpp:13351-13387,13423-13429` — 値の読み取り、pipeline windows との排他、flag 確保・設定、起動ログ。
- `engine/src/program/generate.cpp:6532-6582` — `--pipeline-windows` の自動選択条件。
- `engine/include/strata/core/verify.hpp:215-225`、`engine/src/core/verify.cpp:1642-1651,2998-3013,3705-3708,3840-3846,4123-4139` — Verifier の hand-off wait/publish と chain の実行。
- `engine/include/strata/kernels/verify_kernels.hpp:109-118`、`engine/src/core/verify.cpp:658-664,3696-3702` — ready flag と timeout。
- `engine/src/program/generate.cpp:22990-22994` — serve decode のエラー出力と終了。
- `docs/MULTI_GPU.md:155,172-178,286-300` — 利用条件と資料上の測定値。
