# `FNX_PF_RCCL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP 版 split engine の prompt prefill で、各カードの chunk sum をホストメモリ経由の ring exchange でなく RCCL の all-reduce で合算するかを選ぶ。選択は `Engine::Engine` で行い、成功すると各カードの prefill 状態に RCCL API と communicator を持たせる。値が無効、peer push が使えない、または RCCL 初期化・自己検査が失敗した場合は prompt sum が host exchange に戻る。decode の sum や attention merge の方式はこの変数では選ばない。`engine/src/split/src/engine.cu:123-146`、`engine/src/split/src/prefill.cu:721-755`。

## 値と判定

`std::getenv` の結果を `rccl_decide` に渡し、設定があれば文字列全体を `"0"` と `strcmp` で比較する。数値変換ではない。

| 条件 | unset | 設定時に RCCL を要求する値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP split engine | `RCCL_DEFAULT_ON`（現行値 `true`） | `"0"` 以外の全文字列。例: 空文字、`1`、`00`、`true`、`false`、` 0` | 完全一致する `0` のみ |
| HIP 以外 | 対象の読み取り分岐なし | 該当なし | 該当なし |

空文字は未設定ではなく「設定あり」であり、RCCL を要求する値として扱う。大文字小文字・空白・数値妥当性の検査や範囲判定はなく、`"0anything"` も要求側である。判定は `engine/src/split/src/hip/rccl_dl.hpp:76-89`、既定値は同 `:21-22`、HIP 条件付き呼び出しは `engine/src/split/src/engine.cu:125-143`。

## 有効になる条件

- HIP (`FNX_HIP`) でビルドされた split engine の実行経路であること。RCCL 判定と実装は `#if FNX_HIP` の内側にある。CUDA 版にはこの変数の読み取りがない（`engine/src/split/src/engine.cu:26-29,125-143`; `engine/src/split/src/prefill.cu:726-743`）。
- カード間 peer push が有効であること。peer push は `FNX_PEER` の `"0"` で無効化され、未設定時は `PEER_DEFAULT_ON`（現行 `true`）を使う。要求値が設定されているのに peer push が無効なら、RCCL を開かず host exchange を維持し、理由行を出す。`FNX_PF_RCCL` が未設定で peer push が無効のときは静かなまま host exchange になる（`engine/src/split/src/hip/peer_policy.hpp:17-40`; `engine/src/split/src/hip/rccl_dl.hpp:76-83`）。
- RCCL 共有ライブラリのロード、必要 symbol の取得、communicator 初期化、fp16 all-reduce の自己検査が成功すること。失敗時は RCCL を選ばず host exchange に戻る（`engine/src/split/src/hip/rccl_dl.hpp:35-67`; `engine/src/split/src/hip/rccl.h:39-124`）。
- RCCL のロード先は別変数 `FNX_RCCL_LIB` が空でない値ならその値、そうでなければ `librccl.so.1`。これはライブラリ探索先の指定であり、`FNX_PF_RCCL` の値判定を上書きしない（`engine/src/split/src/hip/rccl_dl.hpp:34-48`）。
- 実際に RCCL を使うのは prompt chunk sum の経路。RCCL が選ばれたとき、`FNX_PF_PEER` による個別 prompt peer sum の `pf_peer_` は無効になる（`engine/src/split/src/engine.cu:144-146`）。

## 実行時の詳細

変数は `Engine::Engine` の起動時に `std::getenv` で一度評価される。実行中に環境値を変えても、保存された `rccl_on_` と `rccl_` の状態には反映されない。判定が要求側で peer push も有効な場合、`rccl_open` がライブラリをロードし、各カードの communicator を作り、各カード 262,144 要素の fp16 all-reduce を自己検査する。自己検査の all-reduce が 30 秒以内に完了しない場合も失敗扱いで host exchange に戻る（`engine/src/split/src/engine.cu:34,134-143`; `engine/src/split/src/hip/rccl.h:39-124`）。

成功時は各カードの prefill sum で RCCL all-reduce を使う。`FNX_PF_RCCL_F32` が非ゼロなら float32 の in-place sum、そうでなければデータを fp16 に pack して all-reduce 後に戻す。RCCL の実行時 all-reduce が失敗した場合は `prefill: ncclAllReduce: ...` の `std::runtime_error` を投げる（`engine/src/split/src/prefill.cu:721-742,1014-1020`）。グループ終了失敗も `prefill: ncclGroupEnd: ...` を投げる（同 `:1413-1430`）。この後段のエラー経路は初期化時 fallback とは異なり、host exchange へ戻す処理はここにはない。

## ログと測定値

- 成功時: `fnx: The prompt sums use RCCL (<ロードしたライブラリ名またはパス>).`（`engine/src/split/src/engine.cu:141`; 文言本体は `engine/src/split/src/hip/rccl_dl.hpp:90`）。
- 設定値があり peer push が無効なとき: `fnx: RCCL is not used for the prompt sums: the peer push between the cards is off, so the host exchange stays.` 未設定で既定が要求側でも peer push が無効ならこの行は出ない（同 `engine.cu:141`; `rccl_dl.hpp:80-82`）。
- ライブラリまたは初期化・自己検査が失敗したとき: `fnx: RCCL is not available here (<理由>): the prompt sums use the host exchange.` 理由の例は `cannot load ...`、`... has no <symbol>`、`ncclCommInitAll: ...`、`the self-test all-reduce did not finish in 30 s`、`the self-test sum was wrong in ... values`（`engine/src/split/src/hip/rccl_dl.hpp:44-63,84-90`; `engine/src/split/src/hip/rccl.h:46-120`）。

現行ソースの `RCCL_DEFAULT_ON` は `true` だが、`docs/SPLIT_ENGINE.md:80` と `engine/src/split/src/hip/rccl_dl.hpp:70-71` の説明コメントは「off by default」と記しており不一致。実際の既定値はコード定数に従う。`engine/src/split/src/hip/rccl_dl.hpp:21-22,76-89`。

## 根拠

- 読み取りと起動時の適用、peer 条件、状態保持: `engine/src/split/src/engine.cu:34,123-146`、`engine/src/split/src/engine.hpp:379-384`
- 値の比較・既定値・分岐ログ: `engine/src/split/src/hip/rccl_dl.hpp:21-22,70-92`
- peer push の既定と判定: `engine/src/split/src/hip/peer_policy.hpp:17-40`
- ライブラリロードと self-test: `engine/src/split/src/hip/rccl_dl.hpp:34-67`、`engine/src/split/src/hip/rccl.h:39-124`
- prompt sum の RCCL 利用とエラー経路: `engine/src/split/src/prefill.cu:721-755,1014-1020,1413-1430`
- 関連説明との不一致: `docs/SPLIT_ENGINE.md:80-81`
