# `INK_RING_CHECK_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling` の `--ring-check` 診断で、prompt IDs をまとめて評価する側の 1 バッチ当たりの token 数（chunk 幅）を指定する。未設定または正数として解釈できない値では 4096 token を使う。これは診断用 CLI の分割幅であり、通常の生成やサーバーの batch size は変更しない。値を読むのは `cmd_ring_check` だけである（`engine/src/inkling2/ink_main.cpp:369-386`）。

## 値と判定

`std::getenv` で設定の有無を確認し、値全体の検証ではなく `std::atoi` の結果が `> 0` かを判定する。正数ならその値を `piece` に採用し、それ以外は初期値 4096 のまま。`atoi` によるため、数値接頭辞の後ろに文字があっても接頭辞が正数なら採用される。空文字や数値接頭辞を持たない文字列は 0 となり既定値になる。文字列の大文字小文字は判定しない。`atoi` の `int` 範囲外の入力は C ライブラリの変換仕様に依存するため、文書上の有効値として扱わない（`engine/src/inkling2/ink_main.cpp:385-386`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `--ring-check` の実行時 | `piece = 4096` | `1`, `+8`, ` 12`, `32tail` は `atoi` が正数を返すためそれぞれ 1, 8, 12, 32 | 空文字、`0`, `-1`, `true`, `0anything` は正数にならず 4096 のまま |

正の値に対する上限 clamp はない。最終バッチは残り token 数までに切り詰める（`engine/src/inkling2/ink_main.cpp:393-397`）。

## 有効になる条件

- `strata-inkling` がビルドされていること。統合ビルドでは `STRATA_BUILD_INKLING` と `STRATA_BUILD_INKLING2` がともに有効で、`engine/src/inkling2` が存在するときに追加される。`ink_main.cpp` はそのサブディレクトリで `strata-inkling` 実行ファイルのソースとして登録される（`engine/CMakeLists.txt:1000-1005`; `engine/src/inkling2/CMakeLists.txt:176-180`）。
- CLI で `--ring-check` に正の stride を指定すること。stride が正でなければこの診断分岐には入らず、この環境変数も読み取られない（`engine/src/inkling2/ink_main.cpp:842-843,968-969,1044-1051`）。
- `--prompt-ids` に ID のリストまたは `@file` を指定し、ID の parse に成功すること。未指定または parse 失敗時は stderr に `--ring-check needs --prompt-ids (a list or @file)` と理由を出して終了コード 2 になる（`engine/src/inkling2/ink_main.cpp:1044-1051`）。
- CPU / CUDA / HIP / Metal / SYCL のいずれかの backend がモデルを開いて初期化できること。モデル open 失敗時は `open: ...`、backend 初期化または slot 確保失敗時は `init: ...` を stderr に出して終了コード 1 となる。環境変数に backend 固有の条件や別の環境変数との優先順位はない（`engine/src/inkling2/ink_main.cpp:376-386`）。

## 実行時の詳細

CLI 引数の解析後、`--info`、export、selfcheck、KLD 評価、reference dump のいずれかが選ばれていればそれぞれ先に return するため、同時に `--ring-check` があってもこの変数は読まれない。それらに該当せず `ring_check_stride > 0` なら prompt IDs を検査し `cmd_ring_check` に進む。この関数はモデルを開き、backend と slot を初期化した後で環境変数を一度読み、比較用の batch chunk 幅を決める。CLI に chunk 幅を直接指定する引数はない。プロセス内での再読み取りや cache はなく、この処理が始まった後の環境変更を反映するコードもない（`engine/src/inkling2/ink_main.cpp:376-386,968-969,1039-1051`）。

処理は、全 prompt IDs を `piece` 以下のまとまりで `forward_batch` に送り、stride ごとの位置と末尾 8 token の logits を保存する。その後 slot を reset し、同じ IDs を一 token ずつ `forward_batch` に送り、同じ行の logits と比較する。したがってこの変数が変えるのは一括評価経路の chunk 分割とその診断比較の形であり、prompt IDs、比較対象の選択規則、通常の生成 token は変えない（`engine/src/inkling2/ink_main.cpp:387-407`）。

一括経路は `forward: ...`、一 token 経路は `step: ...` を stderr に出して終了コード 1 を返し得る。比較結果は全行と `swa_win` 以降について KL median / max と top-1 agreement を stdout に表示する。`swa_win` 以降の行がなければ成功扱い。それ以外ではその範囲の KL median が `0.02` 未満かつ top-1 agreement が 90% 超なら `[ring-check] RESULT: ok` と終了コード 0、条件を満たさなければ `[ring-check] RESULT: BATCH LOGITS DIFFER FROM THE ONE-TOKEN STEPS AFTER THE WINDOW` と終了コード 1 になる（`engine/src/inkling2/ink_main.cpp:418-441`）。

## ログと測定値

診断の stdout に batch 幅を含む `[ring-check] ... batches of %d ...` 行と、比較指標・結果が出る（`engine/src/inkling2/ink_main.cpp:435-441`）。Strata の `docs/DETAILS.md` にこの環境変数に関する記述は見当たらず、本調査で測定は行っていない。

## 根拠

- `engine/src/inkling2/ink_main.cpp:369-386` — 診断の目的、既定値、環境変数の読み取り。
- `engine/src/inkling2/ink_main.cpp:387-407` — 比較行の選択、一括 chunk 処理、一 token 処理。
- `engine/src/inkling2/ink_main.cpp:418-441` — 指標、出力、終了判定。
- `engine/src/inkling2/ink_main.cpp:842-843,968-969,1044-1051` — CLI stride と prompt IDs による到達条件。
- `engine/CMakeLists.txt:1000-1005`; `engine/src/inkling2/CMakeLists.txt:176-180` — standalone executable の build 条件とソース登録。
