# `STRATA_PF_PEER_CPU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

peer GPU を使う prompt prefill でも、条件を満たす native expert layer に CPU share を適用できるようにする opt-in です。通常は peer prefill があると CPU share の候補から外れますが、この変数が有効だとその除外を解除します。CPU share の割合や `--peer-device` の有効化は行いません。実装は `engine/src/prefill/prefill.cpp` の `pf_peer_cpu()` と `run_impl` 内の `cpu_maybe` 判定です（`prefill.cpp:711-714, 5876-5877`）。

## 値と判定

`pf_peer_cpu()` の初回呼び出しで `std::getenv` の値を `std::atoi` に渡し、変換値が 0 以外なら有効として `static const bool` に保存します。したがって未設定と空文字は無効です。`0`、`0abc`、`true`、`false` も `atoi` が 0 にするため無効で、`1`、`-1`、`1abc` は非 0 となり有効です。先頭の空白や符号は `atoi` の変換規則に従い、文字列全体の妥当性や末尾は検査しません。`int` の範囲を超える数値文字列もコードでは検査せず、その場合の変換結果は規定できません（`engine/src/prefill/prefill.cpp:711-714`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `pf_peer_cpu()` を通る実行経路 | 無効 | `1`, `-1`, `1abc` | 空文字, `0`, `0abc`, `true`, `false` |

## 有効になる条件

- peer prefill が存在するとき（`m.pp != nullptr`）に、この変数が有効だと CPU share の peer による除外条件を通過します。peer がない経路ではこの変数は CPU share の可否を変えません（`engine/src/prefill/prefill.cpp:5876-5877`）。
- さらに `pool_hold.held`、`!stream_all`、`m.src != nullptr`、`!m.cpu_dead`、`lay.native`、`!lay.fmt.empty()` が必要です。いずれかを満たさない layer では CPU share を試しません（同 `prefill.cpp:5876-5877`）。
- この変数だけでは CPU share は起動しません。`STRATA_PREFILL_CPU_SHARE` が明示されていれば、その値が CPU share の割合または `auto` 判定を決めます。未設定時は `g_share_default` が armed の場合に限り share が既定で有効になりますが、`--peer-device` を使う通常の非 serve 経路では `generate.cpp` の呼び出しが `!multi_gpu` を既定有効条件に含めるため、その条件では既定 share を arm しません（`prefill.cpp:691-704`; `engine/src/program/generate.cpp:23980-23983`）。serve 経路は別条件で `arm_cpu_share` を呼び、層分割の既定 arm も別の link-rule 条件で判定します（同 `generate.cpp:11890-11906`, `prefill.cpp:3878-3896`）。
- share の chunk 上限と expert ごとの token 上限は、別変数 `STRATA_PREFILL_CPU_SHARE_MAX` / `STRATA_PREFILL_CPU_SHARE_NT` や default-share の条件にも依存します。`STRATA_PF_PEER_CPU` が有効で default share が arm 済み・上限が未指定の場合、`cpu_share_max()` は architecture 固有の default limit を使わず既定値 3072 を返すように分岐します（`prefill.cpp:734-743`）。
- `cpu_maybe` が立っても、実際に CPU に回る expert は routed token があること、peer が計算しないこと、primary cache にないこと、expert の token 数が `cpu_share_nt()` 以下であること、blob が pinned または transient でないこと、share 割合と row 上限を満たすことにも依存します（`prefill.cpp:6017-6057`）。peer が計算する expert は候補から外れます。
- 候補の選定と peer との行配置はこの prompt prefill の処理です。CPU の行は peer の行ブロックより前に置き、peer の行は combine が読む末尾ブロックに保ちます。CPU share を有効化しただけで token 選択規則や peer cache の構成を切り替える実装ではありません（`prefill.cpp:6059-6120, 7588-7630`）。

## 実行時の詳細

`pf_peer_cpu()` は `static const bool` を初回評価して以降の呼び出しで再利用します。よって実行中に環境を変更しても反映されません。プロセス起動直後ではなく、peer 条件付きの CPU share 判定または `cpu_share_max()` の判定から初めて呼ばれた時点で読みます（`engine/src/prefill/prefill.cpp:711-714, 741-743, 5876-5877`）。

peer prefill がある場合、この値は `cpu_maybe` の `(!m.pp || pf_peer_cpu())` 部分だけを変えます。share 割合は `STRATA_PREFILL_CPU_SHARE` と既定 arm 状態から別に決まり、未設定かつ default share が arm されていなければ 0 です（`prefill.cpp:691-704, 5876-5877, 6038-6039`）。CPU share は候補 expert の blob と行を確保し、CPU pool で GPU 側の expert 計算と並行して計算した後、結果行を GPU に戻して通常の MoE combine に渡します（`prefill.cpp:6041-6057, 6206-6248, 7588-7630`）。

必要な pinned activation / rows buffer を確保できない場合は、その engine 実行中の CPU share を停止し、stderr に `prefill: the CPU share is off for this run: the host could not give ... (RAM is short); the GPU streams every expert` を出します（`prefill.cpp:5878-5886, 5914-5918, 5941-5954`）。選定済み CPU expert の出力行や row-scale の確保に失敗した場合は `prefill: cannot allocate the CPU experts' rows` または `prefill: cannot allocate the CPU experts' row scales` を `err` に設定し、その prefill を失敗させます（`prefill.cpp:6208-6232`）。

## ログと測定値

この変数の値だけを示す専用ログはありません。上記の pinned buffer 不足時に CPU share 停止ログが出ます。peer GPU の起動・cache 結果など別のログは `--peer-device` の処理に属し、この変数の有効化ログではありません。

実装コメントには RTX 5060 Ti（PCIe 3.0 x8）+ RTX 3060、IQ3_XXS の会話での測定が記載されています。161–173K token の会話で、tool result を順に読んだとき、117–132 token の応答は 1.80–1.92 秒から 1.16 秒、325–335 token は 2.12–2.89 秒から 1.36–1.63 秒、524 token は 3.33 秒から 1.99 秒、1067 token は 3.74 秒から 2.64 秒、2012 token は 4.33 秒から 4.22 秒、3.2–3.5K token は不変、全体は 36.0 秒から 29.7 秒とコメントされています。これは実装コメントに記録された測定値であり、この調査で再測定した値ではありません（`prefill.cpp:705-710`）。`docs/SETTINGS.md` は変数を number 型・NVIDIA and AMD として一覧に載せていますが、`docs/DETAILS.md` にはこの変数固有の説明は見当たりません。

## 根拠

- `engine/src/prefill/prefill.cpp:705-714` — 実装コメントと値の取得・変換・cache。
- `engine/src/prefill/prefill.cpp:734-743` — chunk 上限の既定値と peer CPU share 時の分岐。
- `engine/src/prefill/prefill.cpp:5876-5886, 5914-5918, 5941-5954` — 有効条件と pinned buffer 不足時の fallback。
- `engine/src/prefill/prefill.cpp:6015-6057, 6059-6120, 6206-6232, 7588-7630` — expert の選定、CPU/peer 行の配置、計算・combine・失敗経路。
- `engine/src/program/generate.cpp:11890-11906, 23980-23983` — serve と通常 generate の CPU share 既定 arm 条件。
- `docs/SETTINGS.md:228` — 候補一覧の型・backend 表記。実装根拠ではない。
