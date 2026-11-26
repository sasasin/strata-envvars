# `STRATA_Q36_OLD_KERNELS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen 3.6 専用 CUDA エンジンの一部の decode 用最適化カーネルを無効にし、従来のカーネル経路へ戻す診断用スイッチである。`Engine::fast_k` はこの変数が未設定なら `true`、設定済みなら `false` になる。したがって値が `1` である必要はなく、空文字を含む設定済みの値はすべて旧カーネルを選ぶ。対象は `engine/src/qwen35/q36_engine.cu` の Qwen 3.6 エンジンであり、Strata の他のモデル経路を切り替える参照はない（同ファイル:2405-2409、`engine/src/program/generate.cpp`:3804-3818）。

切り替わるのは小さい Q8 行列積、RMS 後処理と q8_1 生成、shared expert の gate/up、router と expert grouping、MoE 出力、MTP draft head、および一部の prompt conv tile 経路など `fast_k` を条件にする処理である。無効時は各関数が既存の `k_add_rms`、`native_mmvq`、`group_old`、`k_moe_out`、通常の head 計算などへ進む。通常経路全体や Qwen 3.6 自体を無効にするスイッチではない（同ファイル:2426-2455、2505-2526、2528-2565、2623-2705、2741-2756、3054-3078）。

## 値と判定

`std::getenv(...) == nullptr` だけで判定し、文字列の変換・比較・数値検査はしない。表の「有効」は旧カーネルへ切り替える意味である（`engine/src/qwen35/q36_engine.cu`:2405-2407）。

| 条件 | unset | 有効になる値（旧カーネル） | 無効になる値（高速カーネルを許可） |
| --- | --- | --- | --- |
| Qwen 3.6 エンジンがビルドされ、実行される場合 | `fast_k=true` | 空文字、`0`、`1`、`true`、`false`、`0anything` を含む、設定された任意の文字列 | なし。値が存在すれば旧カーネル側 |

境界値・大文字小文字・空白・文字列末尾は検査されず、設定有無だけが使われる。CLI 引数による上書きや別の値 fallback はない。

## 有効になる条件

- `engine/src/qwen35/q36_engine.cu` を含む CUDA/HIP エンジンがビルドされている必要がある。CMake は `STRATA_HIP_GFX906` の場合にこのエンジンを追加しない（`engine/cmake/strata_gpu_engine.cmake`:565-584）。
- `strata` ではモデルの GGUF architecture が `qwen35moe` の場合に Qwen 3.6 エンジンへ切り替わる。単体の `strata-q36` も同じエンジンを呼ぶ（`engine/src/program/generate.cpp`:3804-3818、`engine/src/qwen35/q36_main.cpp`:1-5）。
- `fast_k=false` は各最適化の他の条件を満たしてもその経路を選ばせない。一方、`T`、行列型・寸法、expert 数、`verify_k` などの条件が満たされない場合は、変数が未設定でも該当最適化は使われない（例: `engine/src/qwen35/q36_engine.cu`:2429-2434、2532-2535、2626-2630、2671-2695、3062-3064）。
- `STRATA_Q36_VERIFY` は別の独立した設定で、設定時には `verify_k` が有効となり、新カーネル経路の一部で旧計算と比較する。`STRATA_Q36_OLD_KERNELS` はこの検証設定を自動では有効にしない（同ファイル:2405-2408、2444-2453）。

## 実行時の詳細

変数名の全参照は、候補登録ファイルや文書上の記載を除くと `engine/src/qwen35/q36_engine.cu:2406` の読み取り 1 箇所である。`Engine` の非 static メンバー `fast_k` の初期化式で環境を読み、`Engine E` の構築時に一度 bool に固定される。構築後にプロセス環境を変更してもこのインスタンスの値は変わらない（同ファイル:1573-1577、2405-2409、5466-5474）。

この bool は個々の最適化の入口で参照される。たとえば Q8_0 の小行列積は条件を満たさないと `false` を返し、呼び出し側が `K::native_mmvq` を実行する。routing/grouping と MoE 出力もそれぞれ既存実装へ進み、prompt の GDN convolution は tile 数を 1 にする。MTP の draft head は高速部分行列計算を使わず、全 vocabulary の `head_rows` に戻る。これらの fallback はモデル全体の出力をどう変えるかをこの変数単独で保証するものではない（同ファイル:2429-2455、2697-2705、2623-2666、2671-2695、2741-2755、3054-3078）。

## ログと測定値

この変数を設定した・未設定であること自体を報告するログ、警告、終了コード変更はない。`STRATA_Q36_VERIFY` を別途設定した場合は各比較の不一致時に `strata-q36 VERIFY MISMATCH ...` が stderr に出て、終了時に比較数と mismatch 数が報告されるが、これは検証設定によるログである（`engine/src/qwen35/q36_engine.cu`:2411-2424、5531-5535）。

`docs/QWEN36.md` は新しい decode kernel が旧カーネルと同じビットを出すとの説明と、`STRATA_Q36_OLD_KERNELS=1` で新カーネルを切る説明を掲載する（118-119行）。そこには Strata 0.1.45、Radeon AI PRO R9700 32 GB / HIP gfx1201、UD-Q4_K_XL、5 組の交互測定などの条件付き速度測定もあるが、環境変数単独の速度差としては記載しない（同文書:121-128）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:2405-2409` — 設定有無の判定と独立した検証フラグ。
- `engine/src/qwen35/q36_engine.cu:2426-2455`, `2505-2526`, `2528-2565`, `2623-2705`, `2741-2756`, `2895-2907`, `3054-3078` — `fast_k` を条件にする処理と fallback。
- `engine/src/qwen35/q36_engine.cu:1573-1577`, `5466-5474` — メンバー初期化と `Engine` 構築。
- `engine/cmake/strata_gpu_engine.cmake:565-584`, `engine/src/program/generate.cpp:3804-3818`, `engine/src/qwen35/q36_main.cpp:1-5` — ビルドおよび実行経路。
- `docs/QWEN36.md:115-128` — decode kernel の説明と条件付き測定。
