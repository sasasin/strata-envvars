# `STRATA_METAL_PROMPT_QSA`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal の streaming prompt 用行列ユニット経路で、QSA attention を `flash` 実装にするか、旧 `v1` の attention と merge にするかを選びます。この変数は prompt 経路そのものを有効化する設定ではありません。prompt の経路選択は `STRATA_METAL_PROMPT`、入力長、streaming の有無などで決まり、その経路が `prompt_chunk()` を使う場合にだけこの設定が使われます。

## 値と判定

`Window::prompt_gemm_init()` が `std::getenv()` で値を取得し、設定されていれば文字列全体を大文字小文字区別で `"flash"` と比較します。数値 parse や先頭文字判定ではありません。

| 値 | 選択される QSA 経路 |
|---|---|
| 未設定 | `COOP_K4` の判定結果 `p.k4` が true なら `flash`、false なら `v1` |
| `flash` | `flash` |
| 空文字、`v1`、`FLASH`、その他の設定値 | `v1` |

設定値が空文字でも「未設定」扱いにはなりません。値が `flash` 以外なら常に `v1` です。`p.k4` は `COOP_K4` が設定されていればその `atoi()` 結果が非ゼロかで決まり、未設定なら Metal 上で協調 tensor のレイアウトを調べる probe の結果です（`metal/src/engine/prompt_chain.inc:26-46`）。したがって未設定時の既定は単純な固定値ではなく、そのレイアウト判定に依存します。

## 有効になる条件

- `STRATA_METAL_PROMPT=window` が設定されていると prompt は decode window 経路になります。この場合、`STRATA_METAL_PROMPT_QSA` は参照されません。`STRATA_METAL_PROMPT` の判定は文字列全体の完全一致です。
- 非 streaming で prompt 長が `STRATA_METAL_PROMPT_MIN`（既定 32）以上の場合は `Window::prompt()` の prompt-chain 実装になります。この経路も本変数を参照しません。
- streaming では、`STRATA_METAL_PROMPT_GEMM` が文字列 `"0"` でなく、prompt 長が `STRATA_METAL_PROMPT_GEMM_MIN`（既定 64）以上なら `prompt_chunk()` を使います。このとき `STRATA_METAL_PROMPT_QSA` が適用されます。`STRATA_METAL_PROMPT_GEMM` は未設定なら有効で、`"0"` との完全一致だけが無効です。
- streaming arena の作成時にも、`STRATA_METAL_PROMPT_GEMM` が `"0"` でなければ prompt GEMM を初期化します。QSA の値はその初期化時に読み取られます。

## 実行時の詳細

`prompt_gemm_init()` は既に `pg_` が作成済みならそのまま成功するため、QSA の variant は `PromptGemm` の初期化時に一度決まり、その window の後続 chunk では再読込されません。初期化ログは stderr に `strata metal: prompts on the matrix units in chunks of ... (experts ..., QSA flash|v1, matmul2d layout ..., ... GB of buffers...)` の形式で出ます。

`flash` 経路は QSA query を FP16 に変換して `qsa_flash` を dispatch し、カーネル内で cooperative `matmul2d` と online softmax を使って attention と出力投影用のゲートを計算します。`v1` 経路は chunk を `QS` 行ずつに分け、`qsa_attn` と `qsa_merge` を dispatch してから出力を FP16 化します。どちらも QSA の選択・top-k の後に attention を計算します。`qsa_flash` は query を half で読み、dequantize した key/value を half の cooperative tensor に変換して演算する一方、`qsa_attn` は float query と float partials を使います（`metal/kernels/qsa_prompt.metal:203-210,227-268`; `metal/kernels/qsa.metal:274-288`）。演算経路が異なるため、出力が常にビット一致するとはソースからは言えません。

## 根拠

- 値の取得、既定値、`p.flash` による scratch buffer の選択とログ: `metal/src/engine/window.cpp:2019-2045,2074,2101-2103`。
- `flash` と `v1` の dispatch 差: `metal/src/engine/window.cpp:2263-2283`。
- streaming prompt が `prompt_chunk()` を使う条件、`STRATA_METAL_PROMPT=window` の分岐、閾値の既定値: `metal/src/engine/window.cpp:2555-2585`。
- streaming arena の初期化時に prompt GEMM を準備する条件: `metal/src/engine/window.cpp:1194-1209`。
- `COOP_K4` の値判定と未設定時の layout probe: `metal/src/engine/prompt_chain.inc:26-46`。
- `qsa_flash` の algorithm と half query / cooperative tensor 実装: `metal/kernels/qsa_prompt.metal:203-268`。`qsa_attn` の float query と float partials: `metal/kernels/qsa.metal:274-288`。
- `docs/DETAILS.md` および Metal 関連資料を確認したが、この環境変数の説明や比較測定値は見つからなかった。性能差・精度差の大きさは、この調査では確認していない。
