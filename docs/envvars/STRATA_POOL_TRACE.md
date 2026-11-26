# `STRATA_POOL_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA 系と SYCL 系の `expert_pool_dispatch_multi` が、verify window の expert pool 処理段階を stderr に出す診断用スイッチ。`expert_pool_dispatch` の通常の単一 token dispatch では読まれず、multi dispatch に入った場合だけ使われる。ログ出力以外にこの変数を使う分岐はなく、pool の割り当て・実行結果を変えない（`engine/src/core/expert_source.cpp:5426-5459`, `engine/sycl/src/core/expert_source.cpp:2559-2591`）。生成側では verify window 用 callback として multi dispatch が登録される（`engine/src/program/generate.cpp:13697-13700`, `engine/sycl/src/program/generate.cpp:7978-7980`）。

## 値と判定

両実装とも `static const bool ptrace = std::getenv("STRATA_POOL_TRACE") != nullptr;` で設定有無だけを見る。値の文字列や数値は解析しない。

| 実装 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA 系 `engine/src/core/expert_source.cpp` | 無効 | 空文字、`0`、`1`、`true`、その他すべての値 | なし（環境変数が存在すれば有効） |
| SYCL 系 `engine/sycl/src/core/expert_source.cpp` | 無効 | 空文字、`0`、`1`、`true`、その他すべての値 | なし（環境変数が存在すれば有効） |

大文字小文字、空白、数値としての妥当性、値の境界は判定されない。CLI 引数・設定ファイル・他の環境変数との優先順位や上書きもない（`engine/src/core/expert_source.cpp:5456-5459`, `engine/sycl/src/core/expert_source.cpp:2588-2591`）。

## 有効になる条件

- 実行ファイルに対応する CUDA 系または SYCL 系実装が含まれていること。コードに OS 判定や実行時 backend 判定はなく、使われる実装はビルドされた経路による。
- `expert_pool_dispatch_multi` が呼ばれる verify window の処理であること。未設定なら段階ログは出ない。
- dispatch がすでに失敗状態ではなく、`n_tok` と `k` が関数冒頭の検査を通ること。範囲外の場合は関数が失敗状態を設定して戻るため、trace 用 static の初期化にもログ出力にも進まない（`engine/src/core/expert_source.cpp:5429-5447`, `engine/sycl/src/core/expert_source.cpp:2562-2574`）。

## 実行時の詳細

値は各 backend 実装の関数内 `static` として、最初に上記の検査を通過して trace 判定箇所へ到達したときに一度読み取られ、その後はプロセス内で cache される。実行中に環境を変更してもこの判定には反映されない。子プロセスへの転送・上書き処理はこの実装にない（`engine/src/core/expert_source.cpp:5456-5459`, `engine/sycl/src/core/expert_source.cpp:2588-2591`）。

有効時は `fprintf(stderr, "pool trace: layer %lld %s %lld\n", ...)` で出力し、各行の後に `fflush(stderr)` する。出力される段階と末尾の数値は次のとおり。

- `begin -1` と `begun -1`: `begin_layer` の前後。
- `publish <fetches>` と `fetch <fetches>`: plan の publish/fetch 処理の前後。CUDA 系では `P.device_hits_only` でない plan 経路、SYCL 系では plan 経路で出る。
- `run <njobs>` と `ran -1`: CPU pool の multi-job 実行の直前と、pool 実行および remote/peer 完了処理を通過した後。

`publish` / `fetch` が出ない経路があり、途中で失敗して早期 return した場合は後続ラベルが出ない。dispatch の範囲エラーや peer GPU の失敗は別の既存経路で処理され、この変数自体が警告・終了・fallback を発生させることはない（`engine/src/core/expert_source.cpp:5692-5695,5933-5956`, `engine/sycl/src/core/expert_source.cpp:2693-2696,2780-2813`）。

## ログと測定値

ログ文言は `pool trace: layer %lld %s %lld`。測定値を出力する機能ではなく、この変数に関連する Strata 資料記載の測定値も確認できなかった。

## 根拠

- `engine/src/core/expert_source.cpp:5426-5459` — CUDA 系 multi dispatch の入口、入力検査、環境読み取りと trace 出力形式。
- `engine/src/core/expert_source.cpp:5469-5471,5692-5695,5933-5956` — begin、publish/fetch、pool 実行と完了後の trace 呼び出し。
- `engine/sycl/src/core/expert_source.cpp:2559-2595` — SYCL 系 multi dispatch の入口、入力検査、環境読み取りと begin trace。
- `engine/sycl/src/core/expert_source.cpp:2693-2696,2780-2813` — SYCL 系 publish/fetch、失敗時 return、pool 実行と完了後の trace。
- `engine/src/program/generate.cpp:13697-13700`, `engine/sycl/src/program/generate.cpp:7978-7980` — verify window 用 multi pool callback の選択。
