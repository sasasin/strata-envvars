# `STRATA_METAL_PROMPT_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal engine の高速 prompt 経路が一度に処理する token 行数を指定する。通常の decode window 経路とは別の prompt chunk 経路で使われ、モデル重みの常駐時と SSD から expert を stream する時で値の上限と既定値が異なる。直接の読み取りは `Window::prompt` と `Window::prompt_gemm_init` にある（`engine/metal/src/engine/window.cpp:3037-3053`, `583-589`）。

この変数は Metal engine 内でだけ参照される。Metal 以外の backend や CLI 側で値を解釈する処理は見つからなかった。prompt の高速経路自体が選ばれない場合、この変数は chunk 処理に使われない。

## 値と判定

どちらの経路も `std::getenv` の文字列を `std::atoi` に渡し、数値全体の妥当性検査や無効値警告はしない。未設定と設定済みの空文字は異なり、空文字は `atoi("") == 0` として最小値へ丸められる。数値の先頭部分だけが変換されるため、たとえば `128tail` は 128、`junk` や `0anything` は 0 として扱われる。最終的な chunk は 64 行単位になる。

| 実行経路 | unset | 設定値の変換と範囲 | 例 |
|---|---|---|---|
| resident（expert stream なし） | 2048 | `atoi` の結果を 64〜8192 に clamp し、その後 64 の倍数へ切り下げる | `0`、負値、`junk`、空文字、`63` → 64。`127` → 64。`128` → 128。`8193` → 8192。 |
| SSD streaming | `hw.memsize` が 96 GiB 以上なら 4096、それ未満なら 1024 | `atoi` の結果に最低値 64 を適用し、64 の倍数へ切り下げる。ソース上の明示的な上限 clamp はない | `0`、負値、`junk`、空文字、`63` → 64。`127` → 64。`128` → 128。8192 より大きい値も切り下げ後の値で使う。 |

この変数の値について `true` / `false` の文字列比較はなく、数値として解釈できない文字列は 0 相当になる。`atoi` の整数範囲外の入力に対する検査や保証は実装にない（`engine/metal/src/engine/window.cpp:3040-3049`, `583-589`）。

## 有効になる条件

- Metal engine の prompt 読み込み経路であること。`Window::init` は `ExpertStream::wanted` の結果で resident / streaming を分ける（`engine/metal/src/engine/window.cpp:714-744`）。
- resident 経路では `STRATA_METAL_PROMPT=window` で window 経路を強制しておらず、prompt 長が `STRATA_METAL_PROMPT_MIN`（既定 32）以上であること。この条件を満たさない場合は `STRATA_METAL_PROMPT_CHUNK` を使う `Window::prompt` に進まない（`engine/metal/src/engine/window.cpp:3743-3748`）。
- streaming 経路では `STRATA_METAL_PROMPT=window` でなく、`STRATA_METAL_PROMPT_GEMM` が文字列 `0` ではなく、prompt 長が `STRATA_METAL_PROMPT_GEMM_MIN`（既定 64）以上であること。満たさない場合は decode window の経路へ進む（`engine/metal/src/engine/window.cpp:3749-3768`）。
- resident の chunk 値は `Window::prompt` の関数内 static に保存される。streaming の値は prompt GEMM 用バッファを初期化する `Window::prompt_gemm_init` で読み、その初期化後は `pg_` があるため再読込しない。したがって、該当経路の初期化後にプロセス環境を変更しても反映されない（`engine/metal/src/engine/window.cpp:3037-3041`, `583-589`）。
- CLI 引数や設定ファイルによるこの環境変数の上書きは、Strata 所有コード内では見つからなかった。

## 実行時の詳細

resident 経路では、初回 `Window::prompt` 呼び出しで chunk 数 `C` を決め、`pc_setup` に最大 prompt 長と 64 行の下限を渡す。その後 prompt 全体を `C` 行以下に分け、各 chunk を `pc_chunk` で処理する。最後の chunk は残り行数だけを処理する（`engine/metal/src/engine/prompt_chain.inc:583-607`）。

streaming 経路では `prompt_gemm_init` が `PromptGemm::MT` を chunk 数 `C` として設定し、必要なバッファを作る。96 GiB 以上の物理 RAM で未設定なら 4096、それ未満なら 1024 が基準値になる。実行時は prompt を `C` 行以下に分割し、各 chunk を `prompt_chunk` に渡す（`engine/metal/src/engine/window.cpp:3037-3053`, `3749-3765`）。

chunk 数が大きいとバッファ需要も増える。streaming ではバッファ用の arena region を確保できない場合に初期化が失敗する。resident の `pc_setup` 失敗、または chunk が context 範囲を越える場合も prompt 処理は失敗を返す（`engine/metal/src/engine/window.cpp:3116-3127`, `3131-3139`; `engine/metal/src/engine/prompt_chain.inc:588-597`）。

## ログと測定値

prompt GEMM の初期化が成功すると stderr に `strata metal: prompts on the matrix units in chunks of %d ...` が出て、採用された行数とバッファ量を示す。streaming で arena region を用いるときは末尾に `, in the expert arena while a prompt runs` が付く（`engine/metal/src/engine/window.cpp:3123-3126`）。resident では `STRATA_METAL_TRACE` が設定されている場合、各 chunk の位置・行数・時間を `strata metal: prompt chunk pos ...` として出す（`engine/metal/src/engine/window.cpp:3455-3467`）。

エラー文字列には `metal prompt: setup failed`、`metal prompt: no arena region for the prompt buffers`、`metal prompt: chunk size out of range`、および context 超過の理由がある（`engine/metal/src/engine/prompt_chain.inc:588-597`; `engine/metal/src/engine/window.cpp:3118-3121`, `3131-3139`）。呼び出し側ではこれらの失敗で prompt 処理を中断して false を返す。ここでは変数値ごとの速度や品質の測定値は記載しない。

`docs/MAC.md` は streaming の既定値（96 GB 以上で 4096、それ未満で 1024）と resident の既定値 2048 を説明しており、ソースと整合する（`docs/MAC.md:74-75`, `269`; `engine/metal/src/engine/window.cpp:3045-3049`, `583-589`）。ただし、同文書は `atoi` の扱い、丸め、resident の上限 8192、streaming で上限 clamp がない点を説明していない。

## 根拠

- `engine/metal/src/engine/window.cpp:714-744` — Metal window 初期化と resident / streaming 判定。
- `engine/metal/src/engine/window.cpp:3037-3053` — streaming 含む prompt GEMM 初期化、既定値と chunk 数。
- `engine/metal/src/engine/window.cpp:3116-3127` — arena region の失敗と初期化ログ。
- `engine/metal/src/engine/window.cpp:3131-3139` — chunk/context の失敗条件。
- `engine/metal/src/engine/window.cpp:3455-3467` — trace ログ。
- `engine/metal/src/engine/window.cpp:3743-3777` — 経路選択、条件、prompt 分割と fallback。
- `engine/metal/src/engine/prompt_chain.inc:583-612` — resident chunk 数の取得、chunk loop、setup/context error、prompt trace。
- `docs/MAC.md:74-75`, `269` — 利用者向けの既定値説明。
