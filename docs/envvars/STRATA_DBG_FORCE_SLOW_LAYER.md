# `STRATA_DBG_FORCE_SLOW_LAYER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系と SYCL 系の prompt prefill にある、融合 MoE バッファの安全確認を layer 0 で意図的に失敗させるデバッグ用フック。値が有効でも遅い expert 計算経路へ切り替えるのではなく、通常は融合経路を取る layer 0 を「融合経路を取らない」と扱って、バッファ不足エラーを返す。環境変数名を含むコメントも「backstop」のテストと説明している（`engine/src/prefill/prefill.cpp:5717-5722`、`engine/sycl/src/prefill/prefill.cpp:3972-3977`）。

## 値と判定

両実装とも `std::getenv` の返す文字列の先頭 1 文字だけを `e[0] == '1'` で比較する。未設定なら無効、空文字も先頭文字がないため無効。値全体の parse、数値検証、trim、大文字小文字変換はしない。先頭が `1` なら後続文字にかかわらず有効で、そうでなければ無効（`engine/src/prefill/prefill.cpp:5718`、`engine/sycl/src/prefill/prefill.cpp:3973`）。

| 実装 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA/HIP 系、SYCL 系 | 無効 | `1`、`10`、`1anything` | 空文字、`0`、`true`、` 1` |

## 有効になる条件

- CUDA/HIP 系または SYCL 系の prefill 実装が使われ、その関数内の MoE 層処理でこの判定に到達すること（読み取りは `engine/src/prefill/prefill.cpp:5718` と `engine/sycl/src/prefill/prefill.cpp:3973`。SYCL 実装は `engine/sycl/CMakeLists.txt:38,304-308` で登録される）。ただし現在の SYCL target は fused kernel の stub をリンクしており、`engine/sycl/src/prefill/prefill.cpp:118-135` の `fused::enabled()` / `native_supported()` は false を返す。標準構成では `fused_ring()` が false となり `m.fused_bufs` も立たないため、この環境変数によるエラー条件には到達しない。SYCL で機能させる構成は checkout の CMake から確認できない。
- チャンクの `m.fused_bufs` が真で、`T >= stream_all_min()` であること。融合レイアウトは expert source があり、融合 ring が有効、MMQ plan に対象層があり、ring が `STAGE` より大きく、チャンクが `stream_all_min()` 以上の場合に選ばれる（CUDA/HIP: `engine/src/prefill/prefill.cpp:2262-2269,2785-2792`; SYCL: `engine/sycl/src/prefill/prefill.cpp:1283-1290,1679-1688`）。
- 判定対象の層が layer 0 であること。layer 0 以外をこの変数だけで強制的に失敗扱いにはしない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5719`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3974`）。
- 失敗条件には `!fused_l` も含まれる。この変数が無効でも、融合レイアウトのバッファを確保したのに層が融合経路を取らない場合は同じ安全確認でエラーになる。CUDA/HIP では peer 利用、stream-all 条件、非 native pack の fused kernel 有効状態、または native format の対応状況が `fused_l` に関与する。SYCL では peer、stream-all、MMQ plan、native format 対応などが関与する（CUDA/HIP: `engine/src/prefill/prefill.cpp:5692-5704`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3962-3965`）。
- CUDA/HIP 系の非 native pack では `STRATA_PF_FUSED` が `fused::enabled()` に影響する。HIP は先頭文字が `1` のとき有効、CUDA は未設定または先頭文字が `0` 以外のとき有効だが、いずれも kernel availability と `pf_fused_override()` による抑止条件がある（`engine/src/prefill/moe_fused.cu:708-721`）。native pack は各層の `native_supported()` が必要（`engine/src/prefill/prefill.cpp:781-805`）。また `--peer-device` 使用時は fused ring が無効になり、この環境変数のエラー条件を成立させない（同: `777-784`）。このデバッグ変数自身を上書きする CLI 引数、設定ファイル、別環境変数はない。対象ソースでの値読み取りは上記 2 箇所だけ。

## 実行時の詳細

値は各実装の関数内 `static const bool` 初期化子で一度だけ読み取られ、以後そのプロセス内でキャッシュされる。したがって読み取り後に環境を書き換えても同じプロセスの判定には反映されない。起動時に必ず読むのではなく、MoE 層のこのコード位置が最初に実行された時点で初期化される（`engine/src/prefill/prefill.cpp:5718`; `engine/sycl/src/prefill/prefill.cpp:3973`）。

条件に一致すると `err` に `prefill: the fused layout's MoE buffers are too small for layer 0's expert path at a chunk of <T> tokens` を設定して `false` を返し、通常の fused/slow expert 計算には進まない。これは意図的に安全確認を発火させるためのフックであり、実際の遅い経路を実行する指定ではない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5719-5722`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3974-3977`）。prefill の失敗は呼び出し元へ伝播し、たとえば CUDA/HIP の単体実行経路と SYCL 実行経路では `forward: <err>` を stderr に出して終了コード 1 を返す（`engine/src/hy4flash/run/hy4_main.hip.cpp:791-796`; `engine/src/hy4flash/sycl/sy_main.cpp:345-351`）。

## ログと測定値

この変数専用の成功ログや値の警告はない。失敗条件に入った場合、呼び出し元が上記のエラー文字列を `forward: ` に続けて stderr に出す。測定値は該当なし。

## 根拠

- `engine/src/prefill/prefill.cpp:5692-5722` — CUDA/HIP 系の融合経路判定、環境読み取り、backstop エラー。
- `engine/sycl/src/prefill/prefill.cpp:3962-3977` — SYCL 系の同じ処理。
- `engine/src/prefill/prefill.cpp:2262-2269,2785-2792`、`engine/sycl/src/prefill/prefill.cpp:1283-1290,1679-1688` — 融合バッファを選ぶ条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:791-796`、`engine/src/hy4flash/sycl/sy_main.cpp:345-351` — 失敗の stderr 表示と終了。
- `docs/DETAILS.md:1348-1366` — `STRATA_PF_FUSED_Q2N` による通常の CUDA fused prompt 経路の説明と条件付き測定。対象のデバッグ変数についての説明や測定ではない。
