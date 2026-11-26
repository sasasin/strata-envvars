# `STRATA_SCORES_THREAD_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP で QSA の prompt block scorer が thread-per-query カーネルを実行する際、stderr に出す engagement 行を制御する診断用変数である。スコア計算カーネルの選択そのものはこの変数ではなく、`STRATA_SCORES_THREAD`、GPU アーキテクチャ、live block 数、query 数で決まる。対象変数はその分岐に入った後のログ出力だけに使われる（`engine/src/kernels/cuda/qsa_select.cu:2232-2249`）。

## 値と判定

`std::getenv` の非 null 判定のみで、値の parse はしない。HIP 分岐で thread scorer が選ばれ、まだそのホスト thread でログを出していない場合、`STRATA_SCORES_THREAD` が未設定（`thread_env == -1`）ならこの変数の有無にかかわらず出力する。`STRATA_SCORES_THREAD` が明示設定されている場合は、この変数が設定済みなら出力する。したがって空文字も設定済みとして有効であり、未設定だけが無効になる（同 `:2234-2247`）。

| 条件 | `STRATA_SCORES_THREAD_TRACE` 未設定 | 設定済みの値 | ログを抑制する例 |
|---|---|---|---|
| `STRATA_SCORES_THREAD` が未設定で、thread scorer の適用条件を満たす | 出力する | 出力する。値は問わない | なし |
| `STRATA_SCORES_THREAD` が設定済みで、thread scorer の適用条件を満たす | 出力しない | 出力する。空文字、`0`、`false`、任意の文字列も設定済みとして扱う | 変数が未設定 |
| HIP 以外 | この変数を読む分岐がない | 同左 | 常に対象外 |

対象変数の空文字・`0`・`false`・大文字小文字・空白・数値形式は検査されない。関連する `STRATA_SCORES_THREAD` は別の static 値として初回評価時に `atoi` され、HIP では `atoi(value) == 1` の場合だけ明示 ON となる（同 `:2234-2240`）。

## 有効になる条件

- HIP コンパイラでコンパイルされた `qsa_select.cu` の分岐である（`engine/src/kernels/cuda/qsa_select.cu:2232-2237`）。CUDA 側には別の scorer 選択分岐があるが、この診断変数を参照しない（同 `:2260-2277`）。
- `qsa_block_scores` が呼ばれ、`active_blocks` が `16385` 以上かつ `max_blocks` 以下、`nq >= 64` であること。さらに gfx12 では `STRATA_SCORES_THREAD=0` でないこと、discrete RDNA3（gfx1100 を含む）では `STRATA_SCORES_THREAD` が `atoi` で `1` になる必要がある。その他の arch は `scores_thread_arch()` が 0 を返し、このカーネルを選ばない（同 `:2234-2240`, `:1282-1296`）。
- 条件を満たす長い prompt の scorer 呼び出しでのみ対象になる。通常の decode は `active_blocks` を渡さない呼び出し経路であり、この条件を満たさない（`engine/src/core/layer.cpp:1277-1280`; prompt 側の live block 数は `engine/src/prefill/prefill.cpp:5375-5391`, `:9445-9455`）。
- 同じホスト thread ではログは一度だけ。初回に対象分岐へ入った時点で対象変数が未設定なら出力されず、後の呼び出しで対象変数を設定すれば出力され得る。すでに出力済みなら以降は出ない（`engine/src/kernels/cuda/qsa_select.cu:2241-2247`）。

## 実行時の詳細

`STRATA_SCORES_THREAD` の判定は関数内 `static` lambda で初回に cache される。一方、対象変数の `getenv` はログ条件が必要な呼び出しごとに評価され、同じホスト thread が一度ログを出すと `thread_local logged` により再評価・再出力されない。従ってプロセス起動後でも、ログ未出力の thread では対象変数の変更が次の適格な呼び出しに反映されるが、`STRATA_SCORES_THREAD` の変更は static 初期化後に反映されない（`engine/src/kernels/cuda/qsa_select.cu:2234-2247`）。

ログ判定後は `block_scores_thread_kernel` と tail kernel を起動し、起動エラーがあれば stderr に `qsa exact thread: <CUDA/HIP runtime error text>` を出して `exit(1)` する。このエラー処理も対象変数の値では変わらない（同 `:2248-2258`）。

## ログと測定値

出力は stderr の次の一行で、`nq`、live block 数、capacity を含む。文言上、score は bit-for-bit 同一と説明されている（`engine/src/kernels/cuda/qsa_select.cu:2242-2246`）。

```text
qsa exact thread: the prompt's block scorer runs as the four-lanes-per-query kernel (nq=... active_blocks=... capacity=...; the same scores bit for bit; STRATA_SCORES_THREAD=0 turns it off)
```

`docs/AMD_HIP.md:350-355` は `STRATA_SCORES_THREAD_TRACE=1` で engagement line を出すと要約している。実装では値 `1` の比較ではなく設定有無を確認し、`STRATA_SCORES_THREAD` 未設定かつ gfx12 の既定経路では trace 変数なしでも出力する。測定値は trace 変数の効果を示すものではないため、ここでは記載しない。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2232-2258` — HIP の環境値判定、ログ条件・文言、kernel launch と失敗経路。
- `engine/src/kernels/cuda/qsa_select.cu:1282-1296` — discrete RDNA3 / gfx12 の arch 判定と device cache。
- `engine/src/prefill/prefill.cpp:5375-5391`, `:9445-9455` — prompt scorer 呼び出し時の live block 数と fallback。
- `engine/src/core/layer.cpp:1277-1280` — decode 呼び出し。
- `docs/AMD_HIP.md:350-355` — 関連説明との照合（現在の値判定の根拠はソースコード）。
