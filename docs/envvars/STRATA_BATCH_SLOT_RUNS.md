# `STRATA_BATCH_SLOT_RUNS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP の batch verifier で、同じ batch slot に属する連続行（その slot の token と提案 token など）を run としてまとめ、対応する QSA indexer append、block score/top-k/attention、および対応形式の KV append を複数行単位で起動する opt-in です。未設定時は従来どおり行ごとの経路です。制御値を読むのは `Verifier::record_window` で、実際に run 化する条件は `batch_rec_ && dec_batch && slot_runs_env` です（`engine/src/core/verify.cpp:1489-1501`）。

これは batch slot のスケジューリング自体を有効化する変数ではありません。batch window の記録時だけ参照され、通常の単一 session window では `batch_rec_` が false のため効きません（`engine/src/core/verify.cpp:4677-4690`）。同じ slot の行数が 1 の場合もまとめる行がなく、起動単位は実質変わりません。各 run は `brow_` の連続した同一 slot 番号で区切られます（`engine/src/core/verify.cpp:1497-1501`）。

## 値と判定

値は `std::getenv` で読み、値が設定されていて `std::atoi(v) != 0` の場合に環境フラグを true にします。文字列全体の厳密な数値検証ではなく、`atoi` の変換結果だけを判定します（`engine/src/core/verify.cpp:1495-1496`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_DEC_BATCH` が unset または `atoi` の結果が非 0 | `STRATA_BATCH_SLOT_RUNS` は false | `1`, `2`, `-1`, `2tail` | 空文字, `0`, `0anything`, `true`, `false` |
| `STRATA_DEC_BATCH` の `atoi` 結果が 0 | `STRATA_BATCH_SLOT_RUNS` に関係なく無効 | なし | すべて |

`STRATA_BATCH_SLOT_RUNS` が未設定なら false、明示的な空文字も `atoi("") == 0` となるため false です。先頭の空白や符号は `atoi` の変換規則に従い、たとえば `  +1tail` は非 0 となります。数値に変換できない先頭（`true` など）は 0 です。末尾の文字列は検査されず、範囲外整数に対する明示的な検査や fallback もありません（`engine/src/core/verify.cpp:1495`）。

`STRATA_DEC_BATCH` は同じ関数内で別の `static` bool として読みます。これは unset なら true、設定値を `atoi` して 0 以外なら true です。したがって明示的な `STRATA_DEC_BATCH=0` は本変数の値が非 0 でも機能を無効にします（`engine/src/core/verify.cpp:1489-1496`）。この機能に対応する CLI 引数による上書きはこの実装箇所にはありません。

## 有効になる条件

- batch slot の窓を `Verifier::capture_batch` が記録し、`record_window` が `batch_rec_ == true` で呼ばれること。batch window は `capture_batch` 内で slot 行を `brow_` に設定して記録されます（`engine/src/core/verify.cpp:4677-4690`）。
- `STRATA_BATCH_SLOT_RUNS` が未設定でなく、`atoi` の結果が 0 以外であること（`engine/src/core/verify.cpp:1495-1496`）。
- `STRATA_DEC_BATCH` が unset または `atoi` の結果が 0 以外であること（`engine/src/core/verify.cpp:1489-1496`）。
- 実装は CUDA/HIP verifier の batch capture 経路です。Metal は `Verifier::init` で専用 window の初期化後に戻り、Metal window 実装は `engine/metal/src/engine/window.cpp` に分かれています（`engine/src/core/verify.cpp:978-993`; `engine/metal/src/engine/window.cpp:1-3`）。SYCL 側の verifier は別実装 `engine/sycl/src/core/verify.cpp` で、この名前の読み取りはありません。
- 複数行をまとめる効果は、対象 layer に複数の連続行が同じ slot について存在するときに現れます。通常は slot ごとに 1 行なら run は 1 行です。複数の提案行がある場合の例は `--batch-mtp` で、実装コメントは各 slot の token と proposals を一 run として説明しています（`engine/src/core/verify.cpp:1490-1494`）。
- `STRATA_NO_BATCH_KV_STEP` が `env_on` 判定で有効だと、QSA indexer append と量子化 KV append の run 化は抑止されます。判定は未設定・空文字・先頭文字 `0` で off、それ以外の先頭文字で on です（例: `false` も on）。このフラグは namespace scope の `const bool` なのでプロセス開始時に読み取られます。block score/top-k および batch attention の run 化にはこの追加条件はありません（`engine/src/core/verify.cpp:336-339`, `348-349`, `2112-2124`, `2253-2263`, `2377-2409`, `2546-2562`）。
- KV append の複数行版を使うのは `kv_hybrid`、`kv_q4`、`kv_int8` の pool です。通常の float KV pool では `kv_append_step` を各行で呼びます（`engine/src/core/verify.cpp:2377-2409`）。

## 実行時の詳細

`STRATA_BATCH_SLOT_RUNS` と `STRATA_DEC_BATCH` は `record_window` 内の関数ローカル `static const bool` 初期化子で読みます。プロセス内の最初の `record_window` 呼び出しで各値を一度評価し、その後の変更は反映されません。最初の呼び出しが通常 window であっても読み取りは発生しますが、その呼び出しでは `batch_rec_` が false のため `slot_runs` は false です（`engine/src/core/verify.cpp:1489-1496`）。`STRATA_NO_BATCH_KV_STEP` は namespace scope の `g_no_batch_kv` 初期化時に `env_on` で読み取られ、同様に実行中の変更は反映されません（`engine/src/core/verify.cpp:336-339`, `348-349`）。

有効時、`run_end` は先頭行から `brow_` が一致する連続行の末尾を探します。各 slot の行が交互に並んでいるなど連続していなければ、run はそこで分割されます（`engine/src/core/verify.cpp:1497-1501`）。この run 長を使って次の処理をまとめます。

- `g_no_batch_kv` が false の場合、QSA indexer append は複数行なら `native_qsa_indexer_append_steps` を使い、1 行なら既存の単行関数を使います（`engine/src/core/verify.cpp:2112-2124`）。
- QSA block score と top-k は同じ slot の run 長 `m` で処理します（`engine/src/core/verify.cpp:2253-2263`）。batch attention 側でも slot run ごとに block score/top-k、KV resolve、attention を呼びます（`engine/src/core/verify.cpp:2534-2562`）。
- KV append は `g_no_batch_kv` が false で、対象 slot の pool が hybrid/q4/int8 のときに run 単位でまとめます。複数行なら各形式の `*_steps` 関数を使い、1 行なら `*_step` 関数を使います（`engine/src/core/verify.cpp:2377-2409`）。

実装コメントでは、これらを単独 window の行処理と同じ kernel を複数行で呼ぶ形と説明しています。ここで確認できる変化は verifier の GPU 作業のグループ化と起動回数であり、環境変数自身が slot の選択・sampler・出力 token を直接変更する処理はありません（`engine/src/core/verify.cpp:1490-1494`, `2117-2124`, `2253-2263`, `2377-2409`, `2546-2562`）。

## ログと測定値

この変数専用の有効・無効ログや値エラーはありません。batch window の graph は batch key ごとに cache され、既存 graph があれば capture を省略して再利用します（`engine/src/core/verify.cpp:4677-4679`）。capture が成功すると、設定にかかわらず `strata verify: captured the batch window over slots ...` を stderr に出します（`engine/src/core/verify.cpp:4704-4707`）。capture 開始失敗時は `verify: begin batch capture failed`、window の記録失敗時は記録処理が返したエラー、capture 終了失敗時は `verify: end batch capture: ...`、instantiate 失敗時は `verify: batch instantiate: ...` がエラー経路に渡されます（`engine/src/core/verify.cpp:4680-4701`）。いずれも本変数の値そのものを示すログではありません。

コメントには当機能が opt-in で、当初は二枚 GPU での測定前は off とする記述がありますが、条件を伴う測定値は記載されていません。この調査では性能向上を推定しません（`engine/src/core/verify.cpp:1490-1494`）。`docs/DETAILS.md` に本変数の個別記載は見つかりませんでした。

## 根拠

- `engine/src/core/verify.cpp:1489-1501` — env 値の parse、`STRATA_DEC_BATCH` との gate、run の境界。
- `engine/src/core/verify.cpp:336-349` — `STRATA_NO_BATCH_KV_STEP` の読み取りと先頭文字判定。
- `engine/src/core/verify.cpp:2112-2124` — QSA indexer append の run 化。
- `engine/src/core/verify.cpp:2253-2263` — QSA block score/top-k の run 化。
- `engine/src/core/verify.cpp:2377-2409` — KV pool 条件と形式ごとの run append。
- `engine/src/core/verify.cpp:2534-2562` — batch row attention の run 処理。
- `engine/src/core/verify.cpp:4677-4707` — batch graph の cache、capture、作成ログ。
- `engine/src/core/verify.cpp:978-993`; `engine/metal/src/engine/window.cpp:1-3` — Metal window の別経路。
