# `STRATA_METAL_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal エンジンで推論ウィンドウとプロンプト処理の時間・ログ出力を stderr に追加する診断スイッチ。ウィンドウでは head を計算したとき、入力 token と出力 token、logits 上位 2 件と差、処理時間、GPU 時間、dispatch 数を記録する。プロンプトでは処理経路に応じてチャンクごとの時間、またはプロンプト全体の時間内訳と token/s を記録する。ログ以外の計算や token 選択を切り替える分岐はこの変数の読み取り箇所にはない（`engine/metal/src/engine/window.cpp:2111-2122,3466-3467`; `engine/metal/src/engine/prompt_chain.inc:608-611`）。

## 値と判定

すべての読み取り箇所で文字列の内容は parse せず、`getenv` が null かどうかだけを見る。したがって未設定だけが無効であり、空文字、`0`、`false`、`0anything` を含む任意の設定値が有効になる。大文字小文字、空白、数値としての妥当性は検査しない（`engine/metal/src/engine/window.cpp:2111,3466`; `engine/metal/src/engine/prompt_chain.inc:608`）。

| 読み取り箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `Window::finish` のウィンドウ trace | 無効 | 空文字、`0`、`1`、`true` など、値を問わず有効 | なし（null 以外は有効） |
| `Window::prompt_chunk` のチャンク trace | 無効 | 空文字、`0`、`1`、`false` など、値を問わず有効 | なし（null 以外は有効） |
| `Window::prompt` の全体 summary | `STRATA_METAL_PROFILE` も未設定なら無効 | `STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` のどちらかが設定済みなら有効 | 両方とも未設定の場合 |

既定値は未設定時の無効。CLI 引数や設定ファイルの値との優先順位・上書き処理は、この名前の参照箇所にはない。

## 有効になる条件

- macOS 向け Metal エンジンを含むビルドであること。`engine/metal/CMakeLists.txt` は Apple 以外の構成を拒否する。Metal C++ ヘッダーの指定がない場合は runtime と engine をビルドせず、`STRATA_METAL_ENGINE=OFF` でも engine を作らない（`engine/metal/CMakeLists.txt:15-20,83-89,103-111`）。
- ウィンドウ trace は `Window::finish` が呼ばれ、`head` が true であること。head なしの prompt window ではログを出さない（`engine/metal/src/engine/window.cpp:1558,1641,2107-2122`）。
- プロンプトのチャンク trace は streaming の prompt であること、`STRATA_METAL_PROMPT=window` でないこと、`STRATA_METAL_PROMPT_GEMM=0` でないこと、prompt token 数が `STRATA_METAL_PROMPT_GEMM_MIN`（既定 64）以上であることが必要。条件を満たすと `prompt_run_rows` が `Window::prompt_chunk` を呼ぶ（`engine/metal/src/engine/window.cpp:3743-3765,3455-3467`）。
- プロンプト全体 summary は `Window::prompt` が最後まで成功して到達すること。`prompt_run_rows` は `STRATA_METAL_PROMPT=window` でないこと、非 streaming であること、かつ prompt token 数が `STRATA_METAL_PROMPT_MIN`（既定 32）以上の場合にこの経路を選ぶ。条件を満たさない場合は通常の window 処理などに進み、この summary は出ない（`engine/metal/src/engine/window.cpp:3743-3774`; `engine/metal/src/engine/prompt_chain.inc:583-612`）。
- `STRATA_METAL_TRACE` が未設定でも、`STRATA_METAL_PROFILE` が設定されていれば `Window::prompt` の全体 summary は出る。ただしこの代替条件は全体 summary だけにあり、ウィンドウ trace とチャンク trace は有効にしない（`engine/metal/src/engine/window.cpp:2111-2122,3466-3467`; `engine/metal/src/engine/prompt_chain.inc:608-611`）。

## 実行時の詳細

`Window::finish` と `Window::prompt_chunk` は、それぞれ関数内 `static const bool` として初回到達時に設定有無を保存する。その各関数で最初に評価された後に環境を変更しても、対応する trace の判定には反映されない。両関数は別々に cache する。一方、`Window::prompt` の全体 summary は各 prompt 完了時に `getenv` を評価するため、コード上は呼び出しごとの判定である（`engine/metal/src/engine/window.cpp:2111,3466`; `engine/metal/src/engine/prompt_chain.inc:583-611`）。

`Window::finish` は head がある場合に logits の全 vocabulary を走査して最大値と 2 位を求め、`stderr` に位置、`tokens[0]` から `out[0]` への値、上位 logits と margin、経過時間、GPU 時間、dispatch 数を出す。`Window::prompt_chunk` は GPU graph 実行後に prompt 位置、行数、graph 時間を出す。`Window::prompt` は全 chunk と drafter rows の処理が成功した後、総時間、GPU・host・embeddings・PLE・drafter の時間内訳と token/s を出す（`engine/metal/src/engine/window.cpp:2107-2122,3455-3467`; `engine/metal/src/engine/prompt_chain.inc:593-612`）。

trace 自体が `false` を返したり `err` を設定したりする経路はなく、プロンプト処理が途中で失敗して `Window::prompt` を抜けた場合は、完了時の全体 summary には到達しない（`engine/metal/src/engine/prompt_chain.inc:589-612`）。

## ログと測定値

有効なウィンドウでの出力形式は `strata metal: window pos %lld token %d -> %d (top %d %.4f, 2nd %d %.4f, margin %.4f) %.2f ms (GPU %.2f ms, %d dispatches)`。prompt chunk は `strata metal: prompt chunk pos %lld, %d rows: %.0f ms`、prompt 全体は `strata metal: prompt %lld tokens in ... -> %.1f tok/s` で stderr に出る（`engine/metal/src/engine/window.cpp:2120-2121,3467`; `engine/metal/src/engine/prompt_chain.inc:609-611`）。Strata の資料にこの変数による性能測定値はない。`docs/MAC.md:282` は「Per-window traces」と記載するが、ソースには prompt chunk と prompt 全体の診断ログも実装されている。

## 根拠

- `engine/metal/src/engine/window.cpp:2111-2122` — head window の設定有無判定、上位 logits の走査、stderr 出力。
- `engine/metal/src/engine/window.cpp:3455-3467` — prompt chunk graph の後に設定有無を cache し、チャンク時間を出力。
- `engine/metal/src/engine/prompt_chain.inc:583-612` — prompt 完了時に trace/profile の設定有無を都度確認して全体 summary を出力。
- `engine/metal/src/engine/window.cpp:3743-3774` — prompt の分岐と全体 summary を出す経路の選択条件。
- `engine/metal/CMakeLists.txt:15-20,83-89,103-111` — Metal ビルドの OS 条件、ヘッダー指定、エンジン build option。
