# `STRATA_Q36_NO_EXT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen 3.6 の CUDA エンジンで、複数行を一括処理するときにルーター出力と共有 expert の gate を一つの行列積で計算する経路（`ext`）を選ぶかどうかを切り替える。環境変数が設定されていると、この最適化経路の条件を満たさなくなり、ルーターと共有 gate を別々に計算する。1 行処理はこの変数にかかわらず `ext` 経路を使う。`ext` 経路は共有 gate の値も `logits_r` の末尾に計算し、後段の MoE 合成で利用する（`engine/src/qwen35/q36_engine.cu:2895-2901,3003-3021`）。

この名前は実際の環境読み取りが `engine/src/qwen35/q36_engine.cu:2899` にある。Strata 内の他の完全一致参照は `terminal/data/settings-register.json:38995-39005` の設定レジストリで、そこでは実行時の値を読み取っていない。コメント、文書、テストを含む他のソース参照は見つからなかった。

## 値と判定

値の内容は変換せず、`std::getenv(...) == nullptr` かどうか、つまり未設定か設定済みかだけを見る。したがって `"1"` だけでなく、`"0"`、`"false"`、任意の文字列、空文字 `""` も「設定済み」として扱われる。大文字小文字、空白、数値の妥当性や境界値の検査はない。設定済みのときに無効化されるのは複数行向け `ext` 条件だけで、1 行は `one` が先に真となる（`engine/src/qwen35/q36_engine.cu:2895-2901`）。

| 条件 | 未設定 | 設定済み（例） | 結果 |
|---|---|---|---|
| `T == 1` | — | `1`、`0`、`false`、空文字 | 常に `ext` 経路。`one` が先に真となるため、この条件では `getenv` も評価しない。 |
| `2 <= T <= 8`、かつ他の `ext` 条件も成立 | `ext` 条件を通過 | `1`、`0`、`false`、空文字、その他任意の文字列 | 未設定なら他条件次第で `ext` 経路。設定済みなら別計算経路。 |
| その他 | — | 任意 | この変数の有無にかかわらず、この複数行 `ext` 条件は成立しない。 |

## 有効になる条件

- 判定箇所に OS や build macro による分岐はない。実装は CUDA API を使う `q36_engine.cu` にある。調査では build を行っていないため、個々の build への組み込みは確認していない（`engine/src/qwen35/q36_engine.cu:2895-2901`）。
- 複数行で `ext` を使うには、`STRATA_Q36_NO_EXT` が未設定で、`STRATA_Q36_OLD_KERNELS` が未設定（`fast_k` が真）、`STRATA_Q36_VERIFY` が未設定（`verify_k` が偽）である必要がある。さらに行数 `T` は 8 以下、モデルの expert 数 `g.n_expert` は 256、`Kp` は 8 でなければならない。`kGemmT` は 8（`engine/src/qwen35/q36_engine.cu:2392-2394,2405-2407,2895-2901`）。
- `STRATA_Q36_NO_EXT` が設定されていても、`T == 1` では `one` により `ext` が選ばれる。`STRATA_Q36_VERIFY` の設定や `STRATA_Q36_OLD_KERNELS` の存在も、この1行の分岐を変えない（同 `:2405-2407,2895-2901`）。
- `T > 8` の prompt chunk、expert 数が 256 以外のモデル、`Kp` が 8 以外の場合は、この複数行向け最適化は使われない。ここでいう `T` は1回の forward に渡る行数で、複数セッションの decode バッチや検証 window からも変わり得る（同 `:2895-2901,3767-3801,3998-4006`）。
- ソース上、`STRATA_Q36_NO_EXT` に対応する CLI 引数や別環境変数からの上書きはない。CLI の `--serve` と token 実行はいずれも同じ `Engine::forward` / layer 処理へ進むため、この設定の判定箇所も共通（同 `:3707-3709,3762-3765,4006,5339-5362`）。

## 実行時の詳細

各 layer の MoE 処理で `ext` を判定する。`T == 1` 以外では `std::getenv` をその場で呼び、設定値を読み込んだり保存する専用 cache はない。`fast_k` と `verify_k` は `Engine` の bool 初期化子で `Engine` 生成時に読み取られる（`Engine E` はモデル読み込み後に作られる）ため、この2変数の読み取り時期は対象変数と異なる（`engine/src/qwen35/q36_engine.cu:2405-2407,2895-2901,5458-5467`）。

`ext` が真なら `router_ext`（通常の expert router 行列に共有 gate の重み行を追加したもの）を使い、`n_expert + 1` 行を出力する。偽なら router の `n_expert` 行だけを計算し、後で `sh_gate_inp` による共有 gate の計算を別に行う。後段は `ext` 時には `logits_r + g.n_expert`、それ以外は別計算した `sgate` を共有 expert の gate 入力として渡す。したがってこの変数は expert 数や top-k の設定自体を変えず、router と共有 gate の計算のまとめ方を変える（同 `:1265-1270,1483-1492,2895-2907,3018-3021`）。

`use_graph` が有効なときは `graph_run` が初回に限り `body()` を capture し、そのときに決まった `ext` 経路を実行グラフに記録する。以降そのグラフキーを再利用する呼び出しでは `body()` を再実行せず、捕捉済みグラフを launch する。従って実行中にプロセス内の環境値を変更する実装があったとしても、既に capture 済みのキーには反映されない。グラフが無効なら body が毎回実行され、`T == 1` 以外の分岐で `getenv` が再評価される（同 `:3612-3635,3707-3709,3762-3765`）。

## ログと測定値

この変数の設定・未設定や `ext` 選択を示す専用ログ、警告、終了コードはない。行列計算中に `cublasSgemm` が失敗した場合は `strata-q36: cublasSgemm failed` を stderr に出して `exit(1)` するが、これは `f32mm` の一般的な失敗経路であり、この変数専用の失敗ではない。測定値は Strata の `docs/DETAILS.md` に見つからず、性能差や出力の数値的一致はここでは主張しない（`engine/src/qwen35/q36_engine.cu:2361-2388`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:2895-2907` — `one`、env 有無、`fast_k` / `verify_k`、行数・expert 数・top-k の判定、および router 計算。
- `engine/src/qwen35/q36_engine.cu:1265-1270,1483-1492,3003-3021` — router 行列と拡張行列の構築、共有 gate の別計算と後段への入力。
- `engine/src/qwen35/q36_engine.cu:2392-2407,3612-3635` — 8行境界、他の2環境変数の初期化、CUDA Graph capture と再利用。
- `engine/src/qwen35/q36_engine.cu:3707-3709,3762-3801,3998-4006,5458-5467` — 通常の1行処理、バッチ forward、検証 window、Engine の生成時期。
- `engine/src/qwen35/q36_engine.cu:2361-2388` — `f32mm` の計算経路と cuBLAS 失敗時の stderr / 終了。
- `terminal/data/settings-register.json:38995-39005` — 候補一覧レジストリ上の記録。実行時の読み取り根拠ではない。
