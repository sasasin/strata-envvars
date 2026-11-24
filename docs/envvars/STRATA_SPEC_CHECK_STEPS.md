# `STRATA_SPEC_CHECK_STEPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling` の `--spec-check N` 診断で、通常の 1-token decode（plain B=1）の prefill と各 decode step の logits ハッシュおよび top-1 token ID を `[steps]` 行として stdout に出します。モデル計算や生成結果の選択を切り替える値ではなく、比較用の出力を追加するだけです。ログ出力は `cmd_spec_check` 内の plain run に限られ、投機実行や verify-window の比較自体を有効化・無効化しません。`STRATA_SPEC_CHECK_STEPS` を読むのは `engine/src/inkling2/ink_main.cpp` の `cmd_spec_check` です（同ファイル 599-600, 632-648 行）。

この読み取りが行われるには `--spec-check` に正の N を渡し、`--prompt-ids` に ID リストまたは `@file` を指定して `cmd_spec_check` へ到達する必要があります。N は `std::atoi` で変換され、変換結果が正の場合だけ診断分岐に入ります。prompt IDs がない場合は stderr に `--spec-check needs --prompt-ids (a list or @file)` を出して終了コード 2 となり、この環境変数の読み取りには進みません（同 966-967, 1062-1069 行）。

## 値と判定

C++ の `std::getenv` で取得し、値が存在して先頭文字 `e[0]` が `'1'` の場合だけ有効です。文字列全体の解析、数値変換、空白除去、大文字小文字変換はありません。未設定と空文字は無効です。先頭が `1` なら残りの文字列は問わず有効で、先頭が `1` 以外なら無効です（`engine/src/inkling2/ink_main.cpp:637`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `cmd_spec_check` の plain run | 無効 | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1` |

CLI 引数や他の環境変数との値の優先順位はありません。この値は診断行を出すかだけを決めます。`--spec-check` の正の N と prompt IDs は処理を実行する別個の条件です（同 1062-1069 行）。

## 有効になる条件

- Inkling-2 の `engine/src/inkling2/ink_main.cpp` を使う実行ファイルで `--spec-check N` の N が正であること。別のエンジンにある同名の `--spec-check` が、この環境変数を読む根拠にはなりません（同 599-600, 1062-1069 行）。
- `--prompt-ids` にパース可能なリストまたは `@file` を与えること。未指定または不正な入力では診断処理に入らず、上記の引数エラー経路になります（同 1062-1069 行）。
- 少なくとも最初の prefill が成功すること。prefill が失敗すると `[steps]` 行を出さず、エラーを stderr に出して終了コード 1 になります（同 616-628, 632-642 行）。
- OS、GPU backend、build macro、サーバーモードによる追加条件は、この読み取り箇所にはありません。`--cpu` などで選ばれる backend は同じ `cmd_spec_check` に渡されます（同 599-609, 918-919 行）。

## 実行時の詳細

値は `run_plain` 内の関数ローカル `static const bool` 初期化で評価されます。初回の plain run で、prefill 成功後に初めて判定され、その後はプロセス内でキャッシュされます。実行中に環境を変更しても再評価されません（`engine/src/inkling2/ink_main.cpp:632-642`）。

`cmd_spec_check` は plain B=1 の生成を 2 回行い、どちらの run にも logits hash 用ポインターを渡します。フラグが有効なら、各 run で prefill 完了後に `[steps] prefill <hash> top1 <id>` を出し、各 decode の `forward_batch` 成功後に `[steps] <step-index> <hash> top1 <id>` を出します。step index は hash を追加する前の `hashes->size()` です。値は `fnv_f32` で logits の全 `V` 個の float のメモリ表現をハッシュした 16 桁の 16 進数で、top1 は `argmax_f32` の ID です（同 588-597, 642-652, 656-658 行）。

この変数はその `[steps]` 行を抑制するだけで、後続の plain 同一性確認、投機実行との token 比較、verify-window および tap の比較を変更しません（同 659-823 行）。prefill または decode が失敗した場合はそれぞれ `prefill: ...` または `decode: ...` を stderr に出し、処理はエラー終了します。その失敗した forward のハッシュ行は出ません（同 623-627, 642-648 行）。この環境変数自体が終了コードや失敗を変える分岐はありません。

## 根拠

- `engine/src/inkling2/ink_main.cpp:599-609` — `cmd_spec_check` の開始、モデル/backend 初期化。
- `engine/src/inkling2/ink_main.cpp:616-652` — prefill、環境変数の static 判定、plain run の `[steps]` 出力と失敗経路。
- `engine/src/inkling2/ink_main.cpp:656-658` — ハッシュ収集を伴う plain run が 2 回行われる。
- `engine/src/inkling2/ink_main.cpp:659-823` — 以降の比較処理と結果出力。
- `engine/src/inkling2/ink_main.cpp:966-967, 1062-1069` — CLI オプションと `--prompt-ids` 条件。
- `terminal/data/settings-register.json:45146-45174` — 候補一覧の補助的な登録情報。挙動の根拠は上記の実行コード。
