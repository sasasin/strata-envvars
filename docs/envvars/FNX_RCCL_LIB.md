# `FNX_RCCL_LIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata リポジトリの作業ツリーは `main`、`origin/main` と一致し、未コミット変更はありません。外部ライブラリ自身の環境変数動作は対象外です。

## 役割

HIP 版の `strata-split` が prompt の chunk sum に使う RCCL ライブラリのロード名を上書きします。ライブラリを見つけられない、必要なシンボルがない、または初期化時の自己テストに失敗した場合、Strata は RCCL を使わず prompt sum を host exchange に戻します。名前を読むのは `src/split/src/hip/rccl_dl.hpp` の `rccl_load()` だけです。テストコードにも候補名の記載がありますが、本番で値を読む箇所はこの一箇所です。

## 値と判定

| 環境変数の状態 | Strata がロードに渡す文字列 |
|---|---|
| 未設定 | 呼び出し元の `path`。実際の呼び出しは空文字列なので `librccl.so.1` |
| 空文字 | 未設定と同じ。実際の呼び出しでは `librccl.so.1` |
| 空でない文字列 | その文字列をそのまま使用 |

値を数値や真偽値として parse せず、Strata 内で空白除去・大文字小文字変換・パス展開・存在確認もしません。空でない値を `dlopen()` に渡し、ロード失敗時は `dlerror()` の理由を `why` に含めます。ライブラリが開けても、`ncclCommInitAll`、`ncclAllReduce`、`ncclGroupStart`、`ncclGroupEnd`、`ncclCommDestroy`、`ncclGetErrorString` のいずれかが見つからなければ失敗です。呼び出し元の `path` は空で、既定名は `librccl.so.1` です（`src/split/src/hip/rccl_dl.hpp:32-58`, `src/split/src/hip/rccl.h:39-43`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` でビルドした別実行ファイル `strata-split-N` が必要です。この機能は通常の Strata 実行ファイルには適用されません。split は opt-in で、CMake は Linux の CUDA または HIP を対象とし、RCCL ロードコードは `FNX_HIP=1` の HIP ターゲットに入ります。CUDA 版ではこの RCCL 読み取り経路はありません（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,20-27,97-109`）。
- split engine の起動時に peer push が有効である必要があります。`FNX_PEER=0` または未設定時の `PEER_DEFAULT_ON` が false なら RCCL のロード処理に進みません。peer probe が失敗した場合も `peer_on` は false のままです（`src/split/src/engine.cu:81-104`, `src/split/src/hip/peer_policy.hpp:17-39`）。
- RCCL の使用要求が有効である必要があります。`FNX_PF_RCCL` が未設定なら `RCCL_DEFAULT_ON`（この commit では `true`）、設定済みなら文字列全体が正確に `"0"` のときだけ無効で、それ以外（空文字を含む）は有効です。無効なら `FNX_RCCL_LIB` は読まれません。peer push が無効で要求が明示されている場合、stderr に peer push が無効なので host exchange を使う旨が出ます（`src/split/src/hip/rccl_dl.hpp:19-20,67-82`, `src/split/src/engine.cu:95-103`）。

したがって、`FNX_RCCL_LIB` の値だけでは RCCL は有効化されません。起動時に上記条件を満たした場合に限りロード先を選びます。判定・ロードは engine 初期化時に実行され、一度選ばれた `rccl_on_` とロード済み state が prompt 実行で使われます。以後プロセス内で環境を書き換えても再判定されません（`src/split/src/engine.cu:87-104`, `src/split/src/engine.hpp:342-344`, `src/split/src/prefill.cu:760-766`）。

## 実行時の詳細

ロードと自己テストに成功すると、stderr に `fnx: The prompt sums use RCCL (<ロード名>).` と出て、prompt chunk sum が RCCL の all-reduce 経路へ進みます。失敗時は `fnx: RCCL is not available here (<理由>): the prompt sums use the host exchange.` と出て、通常の host exchange に戻ります。明示的に RCCL を要求したが peer push が無効な場合は `fnx: RCCL is not used for the prompt sums: the peer push between the cards is off, so the host exchange stays.` です。未設定の `FNX_PF_RCCL` による既定要求で peer push が無効の場合、この RCCL 不使用ログは抑制されます（`src/split/src/hip/rccl_dl.hpp:67-82`, `src/split/src/engine.cu:90-103`）。

ロード後は communicator をカードごとに作り、fp16 all-reduce の自己テストを行います。初期化エラー、テスト用バッファ確保失敗、30 秒以内に collective が終わらない場合、HIP エラーまたは合計値の不一致もロード失敗扱いとなり、上記の host exchange fallback と理由ログになります（`src/split/src/hip/rccl.h:40-124`）。RCCL 経路に入った後の prompt all-reduce 呼び出しが失敗した場合は `prefill: ncclAllReduce: ...` の `std::runtime_error` を投げます（`src/split/src/prefill.cu:512-534`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:593`。
- 全参照検索では、候補一覧に加え、実装の読み取り `src/split/src/hip/rccl_dl.hpp:34` とテストコードのみが見つかりました。実装の全呼び出し経路は `src/split/src/engine.cu:96-100` → `src/split/src/hip/rccl.h:40-43` → `src/split/src/hip/rccl_dl.hpp:33-36` です。
- split の build 条件: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,20-27,97-109`。
- `docs/DETAILS.md` にこの変数の説明はありません。ソースコメントと現在の値の判定が異なる箇所がありますが、現行値の根拠には実コードを用いました。`RCCL_DEFAULT_ON` は `src/split/src/hip/rccl_dl.hpp:20` で `true`、対して同ファイルの `rccl_decide()` 実装は未設定時にその値を使います（同 `:67-70`）。また `engine.cu:95` のコメントは既定を off と説明しますが、同 `:96` が渡す実値は上記定数です。
