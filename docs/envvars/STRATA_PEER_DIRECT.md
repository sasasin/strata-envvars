# `STRATA_PEER_DIRECT`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CUDA の `--peer-device` expert tier が計算した行を、peer GPU 上の結果バッファから pinned host 出力行へ直接 scatter する経路の選択に使います。既定では直接経路を使います。`0` 相当を指定すると従来経路になり、入力を host staging buffer にコピーし、peer の出力を device-to-host copy した後、`finish()` で host memcpy します。これは peer tier の有効化や P2P 可否そのものを切り替える設定ではありません。実装と切替点は `src/core/peer_experts.cpp:249-256,297-328`、従来経路は同 `:297-302,326-328,330-347` にあります。

## 値と判定

値は `std::atoi` で整数化し、結果が 0 以外なら direct mode、0 なら従来経路です。文字列全体の厳密な数値検証や範囲チェックはありません。

| 設定 | 判定 | 例 |
|---|---|---|
| 未設定 | 有効（既定） | — |
| 空文字 | 無効 | `""` は `atoi` の結果が 0 |
| 整数化の結果が 0 | 無効 | `0`, `00`, `0tail`, `true`, `abc` |
| 整数化の結果が 0 以外 | 有効 | `1`, `-1`, `2`, `1tail`, ` 1x` |

`atoi` が読み取れる先頭の整数部分で判定されるため、後続文字は判定に使われず、数値として読めない文字列は 0 扱いです。読み取り箇所は `src/core/peer_experts.cpp:249-252` です。

## 有効になる条件

- `--peer-device N` で peer tier を構成していること。CLI 解析は `src/program/generate.cpp:3721`、tier の初期化は同 `:8813-8829` にあります。tier には expert profile と expert cache も必要で、不足時は stderr に `strata generate: --peer-device needs --expert-profile and the expert cache` を出して終了コード 1 で戻ります（同 `:8815-8819`）。
- CUDA 実装で peer の `launch()` が、出力先 `out` を受け取ること。実際の呼び出しでは `src/core/expert_source.cpp:5155-5164` から `out` が渡されます。実行時の direct 判定は `direct_mode() && out != nullptr` です（`src/core/peer_experts.cpp:254-256`）。
- peer tier の launch が対応する native expert pack であること。非 native pack は `only native packs are supported` のエラーになります（`src/core/peer_experts.cpp:305-317`）。

CUDA の peer GPU 間 P2P 判定は別処理です。`PeerExperts::open()` は peer access 可否と試験 copy を確認しますが、`STRATA_PEER_DIRECT` の値をそこでは参照しません（`src/core/peer_experts.cpp:145-168`）。CLI 引数や別の環境変数による本設定値の上書きは見つかりません。SYCL では peer tier 自体が未実装で、`open()` は `--peer-device: the second-GPU expert tier is not ported to SYCL yet` を返します。SYCL 側にこの環境変数の読み取りはありません（`sycl/src/core/peer_experts.cpp:19-35`）。

## 実行時の詳細

`direct_mode()` 内の関数ローカル `static const bool` に判定結果を保存するため、初回呼び出し時に一度読み、そのプロセス内では再評価しません（`src/core/peer_experts.cpp:249-252`）。

direct mode では `launch()` が入力を `h_x_` に memcpy せず、渡された `x` から peer の `d_x_` に転送します。計算後は `scatter_rows_f32()` が `d_out_` の結果を `out` の該当行へ直接書き、`launched_direct_` を立てます（`src/core/peer_experts.cpp:297-303,319-324`）。呼び出し元はその行をゼロ初期化しないため、peer の書き込みと競合しません（`src/core/expert_source.cpp:5266-5275`）。`finish()` は stream の完了を待って戻り、host memcpy を省きます（`src/core/peer_experts.cpp:330-347`）。

従来経路では `launch()` が入力を `h_x_` にコピーし、peer 計算結果を `h_out_` へ device-to-host copy します。`finish()` は完了後、`row_of_` に記録した各出力行を `out` に memcpy します（`src/core/peer_experts.cpp:297-302,326-328,330-347`）。direct mode の選択自体について専用ログはありません。

launch に失敗すると呼び出し元は stderr に `strata: <エラー> (layer <番号>)` を出して worker を失敗状態にします。完了待ち側のエラーも同じ形式で報告されます（`src/core/expert_source.cpp:5155-5162,5384-5392`）。CUDA エラー文字列の組み立ては `src/core/peer_experts.cpp:87-91` にあります。

## 根拠

- 読み取り、既定値、整数変換、cache: `src/core/peer_experts.cpp:249-252`。
- direct / staging 経路と行の書き込み: `src/core/peer_experts.cpp:254-328,330-347`。
- worker からの呼び出し、direct 行をゼロ化しない分岐、失敗報告: `src/core/expert_source.cpp:5155-5164,5266-5275,5384-5392`。
- CLI と tier 初期化条件: `src/program/generate.cpp:1234-1240,3721,8813-8829`。
- SYCL の非対応: `sycl/src/core/peer_experts.cpp:19-35`。
- `docs/DETAILS.md` と同梱設計資料に `STRATA_PEER_DIRECT` の追加説明は見つかりませんでした。
