# `STRATA_GDN_REC_HEADS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

GDN（gated DeltaNet）プロンプト再帰で、通常の列分割カーネル群の代わりに、1つのブロック／work-groupで1ヘッドを処理する経路を選ぶ A/B 用スイッチ。出力付きの標準経路では再帰と出力正規化を `gdn_rec_kernel` 内で実行する。CUDA/HIP は `engine/src/prefill/kernels.cu`、SYCL は `engine/sycl/src/prefill/kernels.dp.cpp` に実装がある。通常のモデル生成で GDN 層を処理するときに参照され、CLI オプションで値を設定する実装は見つからなかった。呼び出し元は `engine/src/prefill/prefill.cpp:5193-5210,9333-9344` と `engine/sycl/src/prefill/prefill.cpp:3544-3557`。

出力付きの標準経路でこの切り替えを使う場合、出力正規化を再帰カーネルに融合する。公開ヘッダーはこの one-block-per-head 経路の fused norm が丸めを変えると記しているため、通常経路と出力が同一ビットになるとは扱えない（`engine/include/strata/prefill/kernels.hpp:69-74`）。

## 値と判定

値を parse せず、`std::getenv(...) != nullptr` で設定の有無だけを判定する。unset のときだけ無効。空文字を含め、何らかの文字列が設定されていれば有効になる。`0`、`false`、`0anything`、大文字小文字、前後の空白、数値としての妥当性は検査されない（`engine/src/prefill/kernels.cu:3083-3088,3291-3293,3309-3314`; `engine/sycl/src/prefill/kernels.dp.cpp:2864-2868,2977-2980`）。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP / SYCL の標準 GDN 再帰 | 無効。通常の backend・モデル別選択に従う | 空文字、`1`、`0`、`false`、その他の任意の値 | なし（unset のみ） |

CLI 引数による上書きや、この変数に既定値を設定する Strata のコードは確認できなかった。HIP の gfx12 統合経路はこの変数を見ずに再帰全体を処理する場合がある（「有効になる条件」参照）。

## 有効になる条件

- Strata が CUDA、HIP、または SYCL の GDN 再帰を実行すること。通常の呼び出しでは GDN 層のプロンプト処理中に `gdn_recurrence` が呼ばれる（`engine/src/prefill/prefill.cpp:5204-5210,9340-9344`; `engine/sycl/src/prefill/prefill.cpp:3550-3557`）。環境変数自体に OS・GPU 世代・サーバーモードの制限はない。
- 出力付き標準経路では有効時に backend の one-block-per-head 経路へ進む。CUDA/HIP は `serial && with_out` の分岐で `gdn_rec_kernel` を起動し、SYCL は同カーネルの分岐へ進む（`engine/src/prefill/kernels.cu:3183-3188`; `engine/sycl/src/prefill/kernels.dp.cpp:2864-2886`）。
- CUDA/HIP では `T <= 0` または診断用の variant `2` も同じ kernel 分岐を通るため、その場合は kernel 選択に本変数の設定有無による差がない（`engine/src/prefill/kernels.cu:3183-3188`）。
- `STRATA_GDN_HEAD` が有効でも、ラッパーは `!serial` を条件に含めるため、この変数が設定されていれば AMD の four-lanes-per-column variant は選ばれず、通常 variant に戻る（`engine/src/prefill/kernels.cu:3286-3294,3309-3314`; `engine/sycl/src/prefill/kernels.dp.cpp:2972-2980`）。
- 出力付きの標準経路では、CUDA の chunked/TC/Warp 再帰および HIP の chunked WMMA 再帰は `!serial` 条件を満たせず、通常の one-block-per-head 分岐に進む（`engine/src/prefill/kernels.cu:3092-3098,3150-3164,3183-3197`; `engine/sycl/src/prefill/kernels.dp.cpp:2864-2868`）。SYCL の variant 6（Intel Xe subgroup）も `!serial` が必要なため選ばれない。
- **例外: HIP gfx12 の融合経路。** `prefill.cpp` は HIP で `gdn_conv_recurrence_fused` を先に試し、成功時は通常の `gdn_recurrence` を呼ばない（`engine/src/prefill/prefill.cpp:5196-5209,9334-9342`）。融合実装の条件は `STRATA_GDN_CHUNKED`、`STRATA_GDN_FUSE`、長さ、出力 stride、gfx12 判定であり、`STRATA_GDN_REC_HEADS` の確認はない（`engine/src/prefill/kernels.cu:2243-2265`）。この条件を満たすと本変数を設定していても統合 chunked 経路が使われる。
- **状態更新だけの経路:** CUDA/HIP の `gdn_recurrence_state_only` は `with_out=false` で同じ実装に入る。`serial && with_out` は成立しないため one-block-per-head 融合カーネルにはならず、chunked/Warp 経路を抑えた後、`STRATA_GDN_PIPELINE` の設定に応じた列分割再帰へ進む（`engine/src/prefill/prefill.cpp:5205-5210`; `engine/src/prefill/kernels.cu:3083-3088,3153-3188,3309-3314`）。

## 実行時の詳細

CUDA/HIP の再帰実装、通常ラッパー、状態更新専用ラッパー、および SYCL の再帰実装と通常ラッパーにそれぞれ関数内 `static const bool` がある。各値はその関数が最初に呼ばれたときに初期化され、そのプロセス内ではキャッシュされる。したがって起動後に環境を変更しても、既に初期化された読み取りには反映されない（`engine/src/prefill/kernels.cu:3083-3088,3286-3293,3309-3314`; `engine/sycl/src/prefill/kernels.dp.cpp:2817-2820,2864-2868,2972-2980`）。

標準の出力付き経路は GDN の各プロンプト chunk で再帰関数を呼ぶ。選択後の one-block-per-head カーネルは各 head の state を読み、token ごとに更新し、同じカーネル内で正規化・出力を書き、最後に state を書き戻す（`engine/src/prefill/kernels.cu:599-653`; SYCL の呼び出し分岐は `engine/sycl/src/prefill/kernels.dp.cpp:2864-2886`）。この環境変数自体に timeout、別プロセスへの転送、ログ出力はない。

ほかのコード参照も確認した。`engine/src/prefill/gdn_harness.cu:450-452` と `engine/tests/hip/gdn_stage_bench.cpp:62-64` は値を表示し、`engine/tests/hip/gdn_chunked.cpp:196-200` はテスト開始時に unset にする。これらは製品経路の追加読み取りではない。設定レジストリの記載（`terminal/data/settings-register.json:10885-10925`）や文書・コメントにも名前があるが、別の env helper へ動的に渡す製品コードは見つからなかった。

## ログと測定値

スイッチの有効・無効や選択 kernel を通知する通常ログはない。CUDA/HIP 側では再帰後の `check("gdn_recurrence")` が CUDA の最終エラーを検査する。エラー時、通常の CLI 実行では stderr に `prefill gdn_recurrence: <CUDA error>` を出して exit code 1 で終了する。`--serve` では同じ stderr 行に加えて `strata serve: fatal GPU error (prefill gdn_recurrence: <CUDA error>): the engine ends so that the server can start it again` を stderr に、`ERR fatal GPU error: prefill gdn_recurrence: <CUDA error>` を stdout に出し、exit code 3 で終了する（`engine/src/prefill/kernels.cu:110-117,3276-3279`; `engine/include/strata/core/device_error_exit.hpp:20-35`）。SYCL の `check` はこのファイルでは生成された no-op 実装で、`gdn_recurrence` の明示的なログはない（`engine/sycl/src/prefill/kernels.dp.cpp:126-138,2970`）。

リポジトリの `docs/SETTINGS.md:83` は値を「on / off」と分類しているが、実装上は値ではなく設定の有無で判定するため、空文字や `0` も有効である。`docs/AMD_HIP.md:323-325` は HIP chunked 経路が `STRATA_GDN_REC_HEADS` 設定時に既存再帰へ戻ると説明する。これは通常の HIP 再帰分岐に一致するが、gfx12 の融合経路は別関数でこの変数を検査しない。対象変数固有の性能測定値は、確認したソースと該当資料からは記載しない。

## 根拠

- CUDA/HIP の存在判定と分岐: `engine/src/prefill/kernels.cu:3083-3098,3150-3188,3281-3314`
- CUDA one-block-per-head kernel: `engine/src/prefill/kernels.cu:599-653`
- SYCL の存在判定と分岐: `engine/sycl/src/prefill/kernels.dp.cpp:2817-2888,2972-2980`
- 通常および状態更新だけの呼び出し: `engine/src/prefill/prefill.cpp:5178-5213,9318-9344`; `engine/sycl/src/prefill/prefill.cpp:3544-3557`
- HIP gfx12 融合経路: `engine/src/prefill/kernels.cu:2243-2280`
- kernel variant の説明と丸めに関する記述: `engine/include/strata/prefill/kernels.hpp:69-74`
- 候補一覧: `docs/envvars/000_envvers.md:1080`（候補掲載のみ。実装根拠には使用していない）
