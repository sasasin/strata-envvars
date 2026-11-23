# `STRATA_Q36_KEEP_STAGING`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 エンジンが streamed prompt 用の staging pair を含む VRAM 配置計画に失敗したとき、staging pair を外した hybrid 配置へフォールバックするかを制御する。未設定なら、pair なしの計画も試し、収まれば streamed prompt path を無効にして CPU pool と VRAM resident experts で続行する。設定するとこの計画上の fallback を禁止し、staging pair を含む計画が収まらなければ配置失敗になる。十分な VRAM があれば、設定の有無によらず staging pair を使う計画が選ばれる。読み取りと配置処理は `engine/src/qwen35/q36_engine.cu` の `place_experts()` にある（同ファイル 4247-4263, 4351-4385 行）。

この環境変数は通常の token 選択や decode の計算を切り替えるものではない。staging を保てない場合に、streamed prompt path を落として配置を続けるか、配置を失敗させるかを変える（`engine/include/strata/qwen35/hybrid_fit.hpp:66-77`、`engine/src/qwen35/q36_engine.cu:4370-4385`）。

## 値と判定

`std::getenv("STRATA_Q36_KEEP_STAGING") == nullptr` かだけを判定する。文字列の変換や比較はなく、環境変数が存在すれば fallback 不許可となる。したがって `1` だけでなく `0`、`false`、空文字、その他どの文字列でも同じ判定である。unset のときだけ fallback が許可される（`engine/src/qwen35/q36_engine.cu:4361`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `place_experts()` が streamed hybrid staging を計画する場合 | staging なしの再計画を許可 | `1`、`true`、空文字（すべて設定あり）: 再計画を禁止 | 該当なし。文字列値として無効判定される値はない |

ここで「有効」は fallback を止めるという意味で、staging が必ず確保できる保証ではない。索引元の `docs/SETTINGS.md:431` は `on / off` と分類しているが、実装は on/off の文字列を parse せず、設定有無を見ている。

## 有効になる条件

- 対象は Strata の Qwen3.6 (`qwen35moe`) GPU engine path（`strata-q36` または `strata` が同じ `run()` path を使う場合）。ソースは CUDA runtime API を使い、prompt-kernel 初期化には CUDA/HIP と GPU・quant format による経路差がある（`engine/src/qwen35/q36_engine.cu:1-3, 48-50, 1996-2043, 5441-5454`）。この名前の読み取り自体は `place_experts()` 内にあり、Metal/SYCL 等の別 engine path を制御する根拠はない。
- routed experts が通常の全 VRAM 配置に入らず hybrid 配置へ進み、`STRATA_Q36_CPU_POOL` を含む build で CPU expert pool が使えること。CPU pool がない build では `place_experts()` はこの環境変数を読む前に「`the routed experts (...) do not fit in VRAM, and this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)`」として失敗する（`engine/src/qwen35/q36_engine.cu:4318-4342`）。
- hybrid 配置で `E.use_pf && E.main_hybrid` が真であること。`E.use_pf` は layer ごとの fused / int8 / MMQ / grouped kernel route と `q36_prompt_path_ok()` から決まり、MMQ build と `STRATA_Q36_NO_MMQ`、`STRATA_EXPERT_I8`、`STRATA_PF_FUSED`、GPU と tensor format が route に関係する。`E.main_hybrid` は MTP block だけが hybrid となる `mtp_only` 配置では偽である（`engine/src/qwen35/q36_engine.cu:1996-2043, 4344-4361`）。この条件が偽なら `hin.streamed` が偽となり、計画の staging は 0 のため、この変数は staging fallback を変えない（`engine/include/strata/qwen35/hybrid_fit.hpp:66-70`）。
- 初回の staging pair 付き計画が VRAM 条件を満たさず、pair なしの計画なら収まる場合に、この変数の差が実際の計画結果に現れる。VRAM 空き、`--prefill` / `--chunk`（または自動 chunk と `STRATA_Q36_CHUNK`）、`--expert-vram`、`--expert-slots`、`--batch`、`--max-context`、モデルの experts と MTP 状態などが計画の必要量や余裕に影響する（`engine/src/qwen35/q36_engine.cu:4247-4266, 4351-4370, 5361-5384, 5456-5517`）。`STRATA_Q36_KEEP_PACKED` と `STRATA_Q36_NO_MTP_CPU` も、packed copy の解放および MTP 配置経由で必要 VRAM と hybrid 経路に関係する（同ファイル 4267-4306 行）。

## 実行時の詳細

`run()` は model load と `Engine::init()` の後、`place_experts()` を呼ぶ（`engine/src/qwen35/q36_engine.cu:5458-5466, 5522-5526`）。全 routed experts が予算と余裕内に入る通常配置では、`place_experts()` は全 experts を VRAM に確保して戻るため、この環境変数の読み取り箇所まで到達しない（同ファイル 4318-4335 行）。hybrid 配置では `hin.staging_full` に最大 layer の experts と tail の 2 倍を設定し、`hin.streamed` と環境変数の設定有無を `HybridIn` に渡す（同ファイル 4351-4370 行）。

`hybrid_plan()` はまず streamed path 用 staging pair ありで slot 数と必要 VRAM を計算する。収まらず `allow_drop` が真なら staging なしでも再計算し、後者が収まる場合に限り `dropped_staging` を返す（`engine/include/strata/qwen35/hybrid_fit.hpp:46-77`）。この結果では `E.use_pf=false`、`E.hybrid_t=E.tmax` となり、各 batch は resident GPU experts と CPU pool で処理され、prompt streaming は使わない。`STRATA_Q36_KEEP_STAGING` が設定されている場合は再計算しない。pair ありの計画が収まらなければ `place_experts()` が false を返し、呼び出し元は `strata-q36: <理由>` を stderr に出して status 1 で終了する（`engine/src/qwen35/q36_engine.cu:4370-4385, 5522-5526`）。

環境値は `place_experts()` の計画時に一度取得し、`hin.allow_drop` に保存する。関数内 static cache や request ごとの再読込はない。後続の staging allocation 失敗時にも、この保存値で分岐する。unset なら確保済み staging を解放し、non-streamed hybrid prompt path へ切り替える。設定ありならその場で fallback せず、allocation error を出して配置を失敗させる（`engine/src/qwen35/q36_engine.cu:4361, 4482-4515`）。

## ログと測定値

- 計画段階で staging を落とした場合、stderr に `strata-q36: the streamed prompt path's two staging buffers (...) do not fit the free VRAM (...): prompts are read on the experts in VRAM and the CPU pool instead (slower prompts; a smaller --prefill chunk may keep staging)` が出る（`engine/src/qwen35/q36_engine.cu:4371-4376`）。
- 設定ありで staging pair 付き計画が収まらない場合、エラー文字列は `not enough VRAM left for the hybrid experts' buffers and slots (... MiB needed, ... MiB free after the weights, the context and the sessions): use a smaller --prefill chunk, fewer slots ("parallel" / --batch), a shorter --max-context` で、forced slots の場合は `, or fewer --expert-slots` も付く（同ファイル 4380-4385 行）。呼び出し元が `strata-q36: ` を付けて stderr に出し、status 1 で終了する（同ファイル 5522-5526 行）。
- 計画後に `cudaMalloc` が失敗した場合も差がある。unset なら `strata-q36: prompt staging (E.stage[%d]) did not fit remaining VRAM ...: falling back to non-streamed hybrid prompt path ...` を stderr に出して継続する。設定ありなら `strata-q36: prompt staging (E.stage[%d]) allocation failed ...` を出し、`out of memory: prompt staging ...` として失敗する（同ファイル 4482-4515 行）。
- 対象 commit の資料に、この環境変数による独立した性能測定値はない。ソースの警告は non-streamed fallback の prompt が slower と述べるが、ここではその定量値を示さない。

## 根拠

- `engine/src/qwen35/q36_engine.cu:4247-4342` — 全 VRAM 配置、CPU pool build 条件、hybrid 配置への遷移。
- `engine/src/qwen35/q36_engine.cu:4351-4385` — 環境値の読み取り、staging 計画、fallback、計画失敗。
- `engine/include/strata/qwen35/hybrid_fit.hpp:20-77` — 入力フラグ、VRAM fit 計算、fallback の条件。
- `engine/src/qwen35/q36_engine.cu:4482-4515, 5522-5526` — 実 allocation 失敗時の分岐と終了経路。
- `engine/src/qwen35/q36_engine.cu:1996-2043, 5361-5384, 5456-5517` — prompt path の成立条件、関連 CLI と chunk 設定。
