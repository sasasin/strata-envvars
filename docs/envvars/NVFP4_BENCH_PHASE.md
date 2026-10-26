# `NVFP4_BENCH_PHASE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA 専用の `nvfp4_decode_bench` が呼ぶ `native_expert_grouped()` の測定対象を、gate/up と down のどちらの処理にするか切り替えます。通常の Strata エンジンの実行設定ではなく、`STRATA_BUILD_TESTS` と CUDA が有効なビルドに追加されるベンチマーク実行ファイル専用です。ソース内の直接読み取りはこのベンチマークに一箇所だけあります。

## 値と判定

変数が未設定なら `native_expert_set_mode()` を呼ばず、初期値の phase `0` で全処理を実行します。設定されている場合は `std::atoi()` で整数に変換し、その値を phase として設定します。文字列全体の妥当性検査や範囲制限はありません。先頭に整数として読める部分がなければ `atoi` は `0` になり、数値に続く文字は変換結果に影響しません。空文字も `0` です。

| 設定値（変換後） | `native_expert_grouped()` の処理 |
| --- | --- |
| 未設定、または `0` | gate/up、SwiGLU・量子化、down を実行 |
| `1` | gate/up、SwiGLU・量子化を実行後、down の前に戻る |
| `2` | gate/up と SwiGLU・量子化を飛ばし、down を実行 |
| その他 | gate/up と down の両方を実行。phase `0` 専用の一部 fused gate/up + SwiGLU 経路は選択されない |

たとえば `1tail` は phase `1`、`2.5` は phase `2`、`invalid` は phase `0` になります。負数や `3` は gate/up と down の両方へ進みますが、phase `0` と同一の kernel 選択になるとは限りません。

## 有効になる条件

`nvfp4_decode_bench` ターゲットは `CMakeLists.txt` で `STRATA_BUILD_TESTS` の範囲内にあり、さらに `STRATA_ENABLE_CUDA` が真のときだけ追加されます。通常のエンジンやサーバーからこの環境変数を読むコードは確認できません。実行ファイルの生成条件を満たさない場合、この変数による Strata の動作はありません。

## 実行時の詳細

ベンチマークは入力・CUDA バッファを用意して入力を量子化した後、環境変数を読み、`native_expert_set_mode(-1, phase)` を呼びます。`-1` は exp mode をこの呼び出しでは上書きしない指定で、phase は CUDA kernel 実装のグローバル変数 `g_exp_phase` に保存されます。続く warmup と全計測反復が同じ設定で `native_expert_grouped()` を呼びます。

phase `1` は gate/up と SwiGLU・quantize の処理後に関数を戻すため down kernel を実行しません。phase `2` は gate/up と SwiGLU・quantize の部分を抑止し、その後の down 部分を実行します。この経路では `hq` バッファは `cudaMalloc()` 後に当該関数内で書き込まれずに down 側へ渡されます。phase `0` では一部の fused gate/up + SwiGLU 経路も選択可能ですが、0 以外の値はこの特別な fused 条件を満たしません。したがって、phase `1` と `2` の計測は各段階を個別に実行するベンチマーク経路であり、通常の全段階実行と同じ処理をする設定ではありません。

環境変数はベンチマークの `main()` 内で一度読み取られ、その実行中の warmup と反復に共通して適用されます。ソースに値の変更・再読込の経路はありません。通常のログ形式は phase を表示しません。ファイル上の実装では、CUDA エラー時の `ck()` がエラー内容を stderr に出して終了し、成功時は時間、推定帯域、出力 hash を stdout に出します。

## 根拠

- `CMakeLists.txt:2006-2014,2144-2149` — テスト群内で CUDA 有効時に `nvfp4_decode_bench` を生成。
- `src/kernels/nvfp4_decode_bench.cpp:118-123,131-155` — 環境変数の読み取り、整数変換、mode 設定、warmup と計測反復。
- `include/strata/kernels/iq_kernels.hpp:89` — `native_expert_set_mode(int mode, int phase)` の宣言。
- `src/kernels/cuda/iq_kernels.cu:5010-5032` — 初期 phase と setter の実装。
- `src/kernels/cuda/iq_kernels.cu:5154-5189,5250-5254,5287-5294` — phase による gate/up、SwiGLU・quantize、down の分岐。
- `docs/NVFP4.md:264-274` — `nvfp4_decode_bench` の測定結果と条件の記載。phase 別の測定値は示されていない。
