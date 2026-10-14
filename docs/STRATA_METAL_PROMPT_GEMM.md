# `STRATA_METAL_PROMPT_GEMM`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal engine の SSD expert streaming が有効なとき、一定長以上の prompt prefill を prompt GEMM（matrix units を使う prompt kernel 群）で処理するか、decode window を使う経路へ回すかを制御します。未設定では prompt GEMM が有効です。無効にすると、streaming prompt は decode window を使って `MAXT` 行ずつ実行・commit します。

この変数は、model が streaming されない Metal 経路の prompt kernel 選択には使われません。非 streaming 経路は `STRATA_METAL_PROMPT` と `STRATA_METAL_PROMPT_MIN` で分岐します。

## 値と判定

コードは数値変換をせず、値全体を文字列 `"0"` と比較します。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| `0`（文字列がちょうど `0`） | 無効 |
| 空文字、`00`、`false`、`1`、その他の文字列 | 有効 |

streaming prompt の長さ条件は別変数 `STRATA_METAL_PROMPT_GEMM_MIN` が担い、既定値は 64 です。したがって GEMM が有効でも、prompt 長 `n` がその値未満ならこの経路には入りません。`STRATA_METAL_PROMPT_GEMM_MIN` は `atoll` で変換され、無効文字列は 0 として扱われるため、長さ条件を満たしやすくなります。

## 有効になる条件

- Metal engine が `ExpertStream::wanted(...)` によって expert streaming を選んでいること。モデルが streaming されない場合、この変数による prompt GEMM 判定は行われません。
- `STRATA_METAL_PROMPT` が `window` でないこと。この値が `window` なら streaming / 非 streaming の分岐より先に window prompt 経路を選びます。
- streaming 経路では `n >= STRATA_METAL_PROMPT_GEMM_MIN`（既定 64）であること。

prompt GEMM が選ばれると `prompt_gemm_init()` が必要な scratch buffer と pipeline を初期化し、prompt を `STRATA_METAL_PROMPT_CHUNK` に応じた chunk に分けて処理します。無効または長さ条件未達なら decode window にフォールバックします。

## 実行時の詳細

`prompt_run_rows()` は streaming 経路に入るたびにこの環境変数を読み、値がちょうど `"0"` かを調べます。そのため、この分岐については prompt 呼び出しの間に環境値を変更すれば次の呼び出しで再評価されます。ただし、engine 初期化時に `stream_arena()` も同じ判定を行い、有効なら `make_arena()` に `576`、無効なら `64` を渡します。有効時は arena の初期化後に prompt GEMM も初期化します。この初期設定と後続 prompt の判定が異なるよう起動後に値を変更した場合、必要に応じて `prompt_gemm_init()` が遅延実行されます。環境値を変更しても、既に確保済みの arena の作成引数は変わりません。

有効な prompt GEMM の初期化時には stderr に `strata metal: prompts on the matrix units in chunks of ...` のログが出ます。prompt GEMM の初期化に失敗した場合は prompt 処理が失敗します。window fallback 自体について、この環境変数専用のログはありません。

コード内には `Window::prompt_gemm_on()` という同じ設定を static cache する判定関数もありますが、HEAD 内では呼び出し箇所がなく、現在の分岐根拠にはなりません。実際の prompt 選択は `prompt_run_rows()` の都度読み取りです。

## 文書・測定との照合

`docs/MAC.md` は Metal の通常の fast prompt path と decode window 経路の品質差を記し、`STRATA_METAL_PROMPT=window` を slow / exact fallback として説明しています。一方、この環境変数固有の値判定や streaming 条件の説明は同文書にありません。性能値はこの環境変数の切り替え比較として文書に示されていないため、ここでは記載しません。

## 根拠

- `metal/src/engine/window.cpp:427-435`: expert streaming を選ぶ箇所。
- `metal/src/engine/window.cpp:1127-1128,1194-1209`: streaming arena 初期化時の判定、arena 作成引数、および prompt GEMM 初期化。
- `metal/src/engine/window.cpp:1976-1977`: prompt GEMM と decode window の経路差、および GEMM 最小長の説明。
- `metal/src/engine/window.cpp:2007-2017`: `STRATA_METAL_PROMPT_GEMM` と `STRATA_METAL_PROMPT_GEMM_MIN` の補助判定関数。HEAD 内に呼び出し箇所はありません。
- `metal/src/engine/window.cpp:2019-2037,2093-2103`: prompt GEMM の初期化、chunk とログ。
- `metal/src/engine/window.cpp:2555-2585`: 実際の prompt 経路選択、streaming 時の環境値読み取り、chunk 処理、window fallback。
- `docs/MAC.md:165-166,183-190`: fast prompt path の品質説明と関連する Metal prompt 設定。
