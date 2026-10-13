# `STRATA_PEER_DIRECT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

`--peer-device` で使う peer GPU の decode expert 出力を、従来の pinned host staging buffer と CPU memcpy を経由せず、結果行の出力先 `out` に直接 scatter する経路の選択変数です。unset なら直接経路を選びます。これは出力先への書き込み方法を変えるもので、peer expert tier 自体を有効にする設定ではありません。

## 値と判定

`PeerExperts::launch()` の最初の呼び出し時に `std::atoi()` で値を読み、関数内の `static const bool` に保存します。同一プロセスでは以後再評価されません。

| 値 | `direct_env` | 動作 |
|---|---:|---|
| unset | true | 直接経路を許可（既定） |
| 空文字 | false | staging 経路 |
| 数値として 0 に変換される値（例: `0`, `false`, 数字で始まらない文字列） | false | staging 経路 |
| 0 以外の整数に変換される値（例: `1`, `-1`, `2`, `1tail`） | true | 直接経路を許可 |

判定は真偽値文字列の比較ではなく `atoi()` の変換結果が 0 かどうかです。先頭空白と符号は整数変換で扱われ、数値部分の後ろにある文字列は無視されます。数値部分がない文字列は 0 になります。整数範囲外の入力の結果は保証されません。

実際の選択は `direct = direct_env && out != nullptr` です。環境変数で直接経路を許可していても、呼び出し側が `out == nullptr` を渡せば staging 経路になります。

## 有効になる条件

- peer GPU の expert tier が起動して有効であり、peer に割り当てられた decode expert の処理で `PeerExperts::launch()` が呼ばれる必要があります。通常の単一 GPU 実行では参照されません。
- `expert_pool_dispatch()` は出力バッファを受け取り、それを `PeerExperts::launch(..., out)` に渡します。出力先が null の呼び出しでは直接経路になりません。
- SYCL 版 `sycl/src/core/peer_experts.cpp` は peer tier の stub で、この環境変数を読みません。`--peer-device` 自体も SYCL では利用できない旨をエラーにします。
- プロンプト処理では `PeerExperts` のキャッシュを MMQ 経路から参照し、`PeerExperts::launch()` は呼びません。そのため、この変数はプロンプト出力方法を切り替えません。

`docs/SECOND_GPU.md` は peer tier が CUDA の第二 GPU expert cache であり、decode window と prompt chunk の双方を処理すると説明しています。ソースではこの変数の効果は `PeerExperts::launch()` を使う decode dispatch 側だけです。文書内に `STRATA_PEER_DIRECT` 自体の値規則や既定値の説明は見つかりませんでした。

## 実行時の詳細

peer が担当する entry の activation は、直接経路では verifier が使う mapped `x` から peer GPU の入力領域へコピーされます。計算後、`scatter_rows_f32()` が peer の結果 `d_out_` を host 上の `out` の各 entry 行へ scatter し、`launched_direct_` を立てます。dispatch 側はこのフラグが立った peer 行をゼロ初期化しないため、進行中の scatter と競合しません。`finish()` は peer stream の完了を待ち、直接経路なら host への追加 memcpy を行わずに戻ります。

staging 経路では入力を `h_x_` にコピーしてから peer に転送し、peer 結果を `h_out_` に D2H コピーします。`finish()` が完了を待った後、`row_of_` に基づいて `h_out_` から `out` へ CPU memcpy します。

処理失敗時は peer のエラーを `stderr` に出し、dispatch の失敗状態を記録します。直接経路の成功を示す専用ログはこの箇所にはありません。

## 根拠

- `src/core/peer_experts.cpp:188-193`: `atoi()` による読み取り、static cache、`out` による追加条件。
- `src/core/peer_experts.cpp:227-254,257-273`: 直接 scatter と staging 経路、stream wait 後の処理差。
- `include/strata/core/peer_experts.hpp:62-68`: `out` と `STRATA_PEER_DIRECT=0` の旧経路についての API コメント。
- `src/core/expert_source.cpp:3477-3480,3801-3808,3870-3879,3918-3926`: decode dispatch からの呼び出し、直接書き込み行の保護、完了処理とエラー伝播。
- `src/program/generate.cpp:5448-5464`: `--peer-device` による peer tier の初期化。
- `src/prefill/prefill.cpp:1643-1655,3472-3500,3542-3550`: prompt 側は別の MMQ 経路で peer cache を参照。
- `sycl/src/core/peer_experts.cpp:1-39`: SYCL peer tier stub。環境変数を読み取らない。
- `docs/SECOND_GPU.md:131-172`: peer tier の対応範囲と利用条件の説明。
