# `STRATA_QFUSE_HC_LOCAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の fused hyper-connection multi-read で、入力に Q8_1 出力先 `q8_mixed` があり、重みが BF16 のとき、32 列を一つの block が所有する counter-free の up kernel を選ぶかを切り替える。未設定または `atoi` の結果が非 0 なら `gr_up_q32_kernel` を使い、`0` なら通常の 16 列 up kernel に戻る。対象は Q8_1 の生成方法と fused read の戻り値であり、環境変数自体からログは出ない。実装は `engine/src/kernels/cuda/fused_gr.cu` の `qfuse_hc_local()` と `fused_gr_read_multi_slice()` にある（同ファイル:1554-1557, 4272-4282, 1887-1899）。

この切替が通常の engine で呼ばれるのは `STRATA_GR_FAST_BUILD == 0` のビルド、すなわち HIP で gfx906 以外の場合。CUDA と gfx906 HIP は macro が 1 となり、関連する kernel 選択分岐と counter-free 判定がコンパイル時に除外される（同ファイル:48-53, 1883-1900, 4024-4033, 4274-4278）。

## 値と判定

値は `std::getenv` で取得し、`std::atoi(e) != 0` で判定する。文字列全体の検証はしない。`atoi` が数値として読み取る先頭部分で判定されるため、空文字、数値に変換できない文字列、`0anything` は false、`1`、`-1`、`1tail` は true になる。先頭の空白や符号も `atoi` の変換に従う。範囲外数値の結果は C ライブラリの `atoi` の範囲外変換に依存し、Strata 独自の境界処理はない（`engine/src/kernels/cuda/fused_gr.cu:1554-1557`）。

| build / 入力 | unset | true になる例 | false になる例 |
|---|---|---|---|
| HIP、gfx906 以外。`q8_mixed` が全 token にあり、BF16 重み（`s_down == nullptr`） | true | `1`, `-1`, `1tail` | 空文字, `0`, `0anything`, `true` |
| HIP、gfx906 以外。`q8_mixed` が全 token にあるが、Q8 重みまたは `q8_mixed` がない | `qfuse_hc_local()` 自体は同じ判定だが、counter-free kernel の条件を満たさない | 同上 | 同上 |
| CUDA または gfx906 HIP | 実行時の効果なし | 実行時の効果なし | 実行時の効果なし |

## 有効になる条件

- fused multi-read 経路を実行すること。単一 token の `fused_gr_read()` はこの判定を呼ばない（`engine/src/kernels/cuda/fused_gr.cu:4254-4282, 4528-4550`）。
- `STRATA_GR_FAST_BUILD == 0` であること。現行 macro 定義では HIP gfx906 以外が該当する。CUDA、gfx906 HIP では変数が kernel 選択に影響しない（同ファイル:48-53）。
- counter-free BF16 up kernel の選択には `q8_mixed != nullptr`、`s_down == nullptr`、かつすべての token に `q8_mixed` があることが必要。`q8_mixed` がなければ通常の up kernel、Q8 重み（`s_down != nullptr`）なら `launch_q8_t` 側の判定に進む（同ファイル:4024-4033, 4272-4282）。
- 上流で Q8_1 出力先が設定される必要がある。MTP は `STRATA_QFUSE_HC` が有効なとき `q8_mixed` を渡し、未設定時は HIP gfx12 を既定対象とする（`engine/src/core/mtp.cpp:1137-1157, 1228-1244`）。Verifier では `STRATA_QFUSE` 用の counter buffer が存在すると出力先を設定する（`engine/src/core/verify.cpp:1796-1818`）。これらは出力先を用意する別設定であり、`STRATA_QFUSE_HC_LOCAL` の値を上書きしない。
- `STRATA_GR_RDNA` または `STRATA_HIP_FAST_DEC` により RDNA 専用経路が選ばれると、`fused_gr_read_multi_slice()` は `launch_multi()` より先に `rdna_gr_read_multi()` を呼ぶ。この専用経路の Q8 tail は `q8_cnt` を参照するため、LOCAL が許す counter-free (`q8_cnt == nullptr`) 入力とは整合しない。RDNA 経路で counter-free 入力を使う動作はコード上で保証されていない（`engine/src/kernels/cuda/fused_gr.cu:4279-4302`; `engine/src/kernels/cuda/rdna_gr.cu:339-365, 555-571`）。

## 実行時の詳細

`qfuse_hc_local()` は function-local static を使わず、呼ばれるたびに環境を読み直す。`fused_gr_read_multi_slice()` は最初に `q32_no_cnt = qfuse_hc_local() && a[0].s_down == nullptr` を計算し、`q8_cnt` がない場合でもこれが true なら Q8_1 出力があるものとして `q8` を立てる。全 token の `q8_mixed` がそろわなければ `q8` を false に戻し、全 token の `m.a[t].q8_mixed` を null にする（`engine/src/kernels/cuda/fused_gr.cu:4272-4282`）。

通常の multi-read では、`q8w` でなく `q8_mixed` があり LOCAL が true の場合、`gr_up_q32_kernel` を起動して 32 列単位で mixed とその Q8_1 image を同じ block が書く。LOCAL が false の場合はこの分岐を通らず、通常の 16 列 up kernel に進む。通常 kernel の Q8_1 tail は二つの block の counter と fence を使うので `q8_cnt` が必要（同ファイル:1887-1928, 261-290, 664-710）。MTP のように `q8_cnt` を渡さない呼び出しで LOCAL が false になると、`q8` が false となり Q8_1 destination も外されるため、呼び出し元が別途 `native_quantize_q8_1` を実行する fallback になる（`engine/src/core/mtp.cpp:1229-1248`）。

Q8 重みを使う `launch_q8_t()` にも、LOCAL が true で `q8_mixed` がある場合に counter-free の `gr_up_q8_q32_kernel` を選ぶ分岐がある。false の場合は通常の Q8 up kernel 経路を使う（`engine/src/kernels/cuda/fused_gr.cu:3991-4054`）。ここも `STRATA_GR_FAST_BUILD == 0` の compile guard 内にある。

環境値の判定は static cache されない。一方、MTP 側で `STRATA_QFUSE_HC` を読む判定は static cache され、Verifier の同名判定も static cache される。各々の上流判定は LOCAL とは独立している（`engine/src/core/mtp.cpp:1137-1144`; `engine/src/core/verify.cpp:221-238`）。

## ログと測定値

LOCAL の有効・無効を示す専用ログやエラー処理はない。通常 kernel の起動後に CUDA/HIP エラーが検出された場合は fused read の既存エラー経路が stderr に出力して終了するが、LOCAL 固有の診断ではない（`engine/src/kernels/cuda/fused_gr.cu:4415-4429`）。現行ソースコメントには性能測定値があるものの、LOCAL の比較条件と測定結果を結び付ける記述は確認できないため、性能値は記載しない。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:48-53` — HIP gfx906 / その他 HIP / CUDA の build macro 条件。
- `engine/src/kernels/cuda/fused_gr.cu:1553-1557` — 値の読み取り、既定値、整数判定。
- `engine/src/kernels/cuda/fused_gr.cu:1883-1900, 4024-4033` — 通常 up と Q8 weight up の LOCAL による分岐。
- `engine/src/kernels/cuda/fused_gr.cu:4272-4302` — counter-free の戻り値判定、出力先の除外、RDNA 分岐。
- `engine/src/kernels/cuda/rdna_gr.cu:339-365, 555-571` — RDNA 専用 Q8 tail の counter 使用と有効条件。
- `engine/src/core/mtp.cpp:1137-1157, 1228-1248` — MTP 側で Q8_1 destination を設定する条件と fallback。
- `engine/src/core/verify.cpp:1796-1818` — Verifier 側の Q8_1 destination 設定。
