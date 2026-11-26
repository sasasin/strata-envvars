# `STRATA_REMOTE_SPIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU 上の remote expert / 追加 stage の仕事を CPU 側が待つときに、Strata が GPU 待ちを spin 方式にするかを切り替える。CUDA では追加 device の初期化時に `cudaDeviceScheduleSpin` を指定するか、HIP では remote expert の stream を spin-query で待つかを決める。SYCL 実装は値を取得するが破棄するため、この変数による待ち方の変更はない。値を使った計算結果の分岐はなく、remote expert の出力計算と行の返却処理は同じ経路で続く（`engine/src/core/remote_experts.cpp:83-97, 361-390`; `engine/sycl/src/core/remote_experts.cpp:99-123, 464-474`）。

## 値と判定

文字列の全体や数値は parse せず、環境値の先頭バイトだけを `'0'` と比較する。未設定または空文字は先頭文字が `'0'` ではないため spin 側になる。`0`, `00`, `0anything` は先頭が `'0'` なのでオフ側、`1`, `true`, `false`, ` 0` は先頭が `'0'` ではないのでオン側になる。大文字小文字・後続文字・空白の trim・数値としての妥当性は検査しない（`engine/src/core/remote_experts.cpp:87-89, 372-375`）。

| 実装条件 | unset / 空文字 | spin 側になる設定値 | spin を止める設定値 |
|---|---|---|---|
| CUDA（`STRATA_USE_HIP` と `STRATA_GPU_METAL` が未定義） | `cudaInitDevice` に `cudaDeviceScheduleSpin | cudaDeviceMapHost` を渡す | 先頭文字が `'0'` 以外の値。例: `1`, `true`, `false`, ` 0` | 先頭文字が `'0'` の値。例: `0`, `00`, `0anything` |
| HIP（`STRATA_USE_HIP`） | `cudaStreamQuery` を繰り返す | 先頭文字が `'0'` 以外の値 | 先頭文字が `'0'` の値。`cudaStreamSynchronize` に切り替える |
| SYCL (`engine/sycl`) | 値を取得するだけ | 該当なし | 該当なし |

## 有効になる条件

- CUDA の設定は `RemoteExperts::preflight()` が呼ばれる追加 GPU で有効になる。該当経路には `--expert-cache-device1..3` の remote expert cache と、複数 GPU の layer split がある（`engine/src/program/generate.cpp:3988-3993, 5516-5525, 6667-6675, 8468-8475`）。
- HIP では remote expert cache があり、その layer で helper が実際に計算した行がある場合に `finish()` の待ち方を選ぶ。対象行がなく `group_id_` が空なら、`finish()` は環境値を読む前に戻る（`engine/src/core/remote_experts.cpp:279-300, 361-375`）。
- `--expert-cache-device1..3` を使うには、少なくとも対象 remote cache が設定され、主 GPU の expert cache、`--expert-profile`、expert pool が必要。満たさない場合は `strata generate: remote experts need --expert-profile, a CUDA0 expert cache and the expert pool` を出して終了コード 2 になる（`engine/src/program/generate.cpp:10127-10132`）。
- SYCL の `preflight()` は `getenv` の値を `(void) spin` で破棄する。`RemoteExperts::finish()` は `stream_->wait()` を使い、`STRATA_REMOTE_SPIN` による分岐を持たない（`engine/sycl/src/core/remote_experts.cpp:99-111, 464-474`）。
- `STRATA_GPU_METAL` が定義された共通実装では preflight の読み取り部分がコンパイルされない（`engine/src/core/remote_experts.cpp:86-90`）。Metal 用の remote expert 動作をこの変数が変更する根拠は見つからない。

## 実行時の詳細

CUDA では `RemoteExperts::preflight()` が対象 device の可視性と primary device でないことを確認した後、device context 作成より前に `std::getenv` を呼ぶ。先頭が `'0'` でなければ `cudaInitDevice(device, cudaDeviceScheduleSpin | cudaDeviceMapHost, 0)` を呼び、その戻り値は検査せず、続けて `cudaGetLastError()` の戻り値も無視する。その後 `DeviceScope` で device を選択し、空きメモリを取得する。device 切替や空きメモリ取得の失敗は `err` に設定され、呼び出し側が stderr に出して終了コード 1 にする（`engine/src/core/remote_experts.cpp:71-97`; `engine/src/program/generate.cpp:5520-5525, 6672-6675, 8470-8475`）。

HIP では preflight はこの変数を読まない。helper の出力を待つ `RemoteExperts::finish()` で、`group_id_` が空でない場合に関数内 `static` の初期化式が一度だけ評価される。値がその時点で先頭 `'0'` 以外なら `cudaStreamQuery(stream_)` が `cudaErrorNotReady` の間ループし、完了時のエラーは `check(e, "finish", ...)` で失敗として返る。先頭が `'0'` なら `cudaStreamSynchronize()` を使い、その失敗を同様に返す。したがって初回の実作業付き `finish()` 後に環境を変更しても、このプロセスの HIP `spin` 判定には反映されない（`engine/src/core/remote_experts.cpp:361-386`）。

`finish()` の失敗は expert dispatch 側で `d.failed` と `d.fail` に記録される。出力は完了後に既存の host row へコピーされる。値によって expert の選択や積和計算を切り替える処理はこの経路にない（`engine/src/core/remote_experts.cpp:361-390`; `engine/src/core/expert_source.cpp:5392-5398, 5938-5944`）。

## ログと測定値

変数の値だけを理由にしたログや警告はない。CUDA preflight が成功すると、呼び出し側は `strata generate: CUDA%d context ready, %.2f GiB free before expert arena registration` を stderr に出す。CUDA 初期化 API の戻り値は無視されるため、それ自体の失敗をこの箇所で報告しない。続く device 選択や空きメモリ取得が失敗した場合は、その `err` を stderr に出して終了コード 1 になる（`engine/src/core/remote_experts.cpp:87-97`; `engine/src/program/generate.cpp:5520-5525, 8470-8475`）。

ソースコメントは Windows の helper round trip に約 `0.3 ms` の待ち起床コストがあったと記すが、測定条件・測定方法・回数は示していないため、一般的な性能値としては扱えない（`engine/src/core/remote_experts.cpp:83-85`）。

## 根拠

- `engine/src/core/remote_experts.cpp:71-97` — CUDA/HIP 共通ファイルの preflight、CUDA 初期化フラグ、HIP では未使用の条件。
- `engine/src/core/remote_experts.cpp:361-390` — HIP の static 判定、spin-query / synchronize の分岐、出力行の返却。
- `engine/sycl/src/core/remote_experts.cpp:90-129, 464-480` — SYCL での値の取得・破棄、wait、例外終了。
- `engine/src/program/generate.cpp:3988-3993, 5267-5273, 5516-5525, 6667-6675, 8468-8475, 10127-10132` — CLI cache 指定、適用される追加 GPU 経路、preflight の失敗処理と remote cache の前提。
- `engine/src/core/expert_source.cpp:5320-5334, 5392-5398, 5718-5725, 5938-5944` — helper の begin / finish 呼び出しと実行失敗の伝播。
- `docs/SETTINGS.md:458` — 設定一覧の記載。対象の値判定と backend ごとの実動作は上記ソースで確認した。
