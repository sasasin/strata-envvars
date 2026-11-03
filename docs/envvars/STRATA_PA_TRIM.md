# `STRATA_PA_TRIM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の AMD matrix-core prompt-attention kernel が使う LDS（GPU 共有メモリ）の配置を選びます。`1` は実 query に使わない padding rows を LDS から省き、`2` 以上はそれに加えて V の staged row を 80 bytes から 72 bytes にします。`0` と負値ではどちらの trim も使いません。カーネル内の算術順序は同じで、コメント上は出力値ではなく LDS 使用量と占有可能 block 数を変える実験用設定です。

この変数は `src/kernels/cuda/qsa_prompt_attn.cu` の `pa_launch()` だけで読み取られます。`qsa_prompt_attn_batch()` または gated 版が HIP matrix-core kernel に進んだ場合にだけ評価されます。CUDA の attention kernel 選択では読みません。

## 値と判定

未設定または空文字列なら既定値 `2` です。空文字列以外は `std::atoi()` で変換し、その整数値に応じて kernel template を選びます。

| `atoi` の結果 | 選択 | LDS 上の変更 |
|---|---|---|
| `0` | `TR=0` | trim なし |
| `1` | `TR=1` | padding rows を省く |
| `2` 以上 | `TR=2` | padding rows を省き、V row を 72 bytes にする |
| 負数 | `TR=0` | trim なし |

文字列全体の厳密な数値検証はありません。`atoi` の規則に従い、先頭の空白・符号と数値部分を読み、数値に続く文字は無視します。数値に変換できない非空文字列は `0` となるため trim なしです。たとえば `2abc` は `2`、`true` は `0`、`-1` は trim なしになります。整数範囲を超える入力の結果はこの実装から保証できません。

根拠: `src/kernels/cuda/qsa_prompt_attn.cu:2297-2309`。

## 有効になる条件

- HIP ビルドであること。HIP gfx906 compatibility build (`STRATA_HIP_GFX906`) では gated 経路はコンパイル時に無効で、通常経路も gfx906 では即座に拒否されます。対象 kernel は gfx11 (`gfx110x` / `gfx115x`) と gfx12 (`gfx1200` / `gfx1201`) の WMMA 向けです（`src/kernels/cuda/qsa_prompt_attn.cu:1896-1905,2448-2457,2468-2502`）。
- prompt attention が `qsa_prompt_attn_batch()` または gated 版へ到達し、Q/K/V pool が int8 K/V と scale を持ち、Q4 pool ではなく、shape が `HD=256` / 12 query heads per KV head、capacity・selection IDs・steps・page table が有効であること（`src/kernels/cuda/qsa_prompt_attn.cu:2445-2457,2494-2502`）。
- `STRATA_HIP_WMMA` と GPU 世代が matrix-core 経路を許可すること。gfx11 は `STRATA_HIP_WMMA=1` などで明示的に有効化したとき、gfx12 は Linux では既定有効、Windows では opt-in です。`STRATA_HIP_WMMA=0` ならこの環境変数の値に関係なく通常の FP32 prompt attention に進みます（`src/kernels/cuda/qsa_prompt_attn.cu:2235-2247,2285-2295,2500-2502`）。
- 別の選択要因として、`STRATA_PA_RPF` は既定で有効で、値の先頭文字が `0` のとき無効です。これは chunk の先読み順序を切り替え、`STRATA_PA_TRIM` が選ぶ template のもう一つの軸になります（`src/kernels/cuda/qsa_prompt_attn.cu:2297-2309`）。

CUDA backend では HIP WMMA 分岐を通らず、CUDA の通常の prompt-attention kernel を選びます。Q4 KV、shape/pool 条件の不一致、WMMA 無効、非対応 GPU などで matrix-core helper が拒否した場合、prefill 側は通常の decode-attention または既存 fallback に進むため `STRATA_PA_TRIM` は効果を持ちません（`src/kernels/cuda/qsa_prompt_attn.cu:2448-2457,2460-2503`; `src/prefill/prefill.cpp:4383-4416,7515-7525`）。

## 実行時の詳細

`pa_launch<SPLIT, GATE>()` の最初の呼び出し時に `STRATA_PA_TRIM` を読みます。値は関数 template の各 `<SPLIT, GATE>` specialisation ごとの `static const int` に保存され、同じ specialisation では以後読み直しません。したがって、その読み取り後にプロセス環境を変えても既に評価済みの specialisation には反映されません。別の specialisation が初めて呼ばれた時点では、その時点の環境を評価します。

`TR=1/2` では共有構造体の `part` / `p` 配列の行数を 16 から `G`（12）へ減らし、padding rows の処理を省きます。`TR=2` はさらに V row を 80 bytes から 72 bytes に縮め、ステージングを 8-byte 単位にします。`TR=0` はどちらの変更も使いません。これらの分岐は LDS 配列寸法・格納・padding 処理を切り替えます（`src/kernels/cuda/qsa_prompt_attn.cu:1918-1935,1973-1975,2080-2089,2104-2109`）。

この環境変数自体に対応するログ、警告、無効値エラーはありません。WMMA kernel launch が失敗した場合は `qsa_prompt_attn_batch (wmma): ...; the FP32 prompt attention runs from here on` を stderr に出し、そのプロセスで WMMA を無効化して呼び出し元の FP32 fallback に進みます。この失敗処理は kernel launch 全般の経路であり、特定の `STRATA_PA_TRIM` 値に対する専用処理ではありません（`src/kernels/cuda/qsa_prompt_attn.cu:2365-2370,2432-2439`）。

## 根拠

- 全参照と変換・既定値・template dispatch: `src/kernels/cuda/qsa_prompt_attn.cu:2297-2310`。
- LDS 配列の寸法と TR 分岐: `src/kernels/cuda/qsa_prompt_attn.cu:1918-1935,1973-1975,2080-2109`。
- backend / architecture / `STRATA_HIP_WMMA` の選択: `src/kernels/cuda/qsa_prompt_attn.cu:1896-1905,2235-2295,2432-2503`。
- prefill からの呼び出しと失敗時 fallback: `src/prefill/prefill.cpp:4383-4416,7515-7525`。
