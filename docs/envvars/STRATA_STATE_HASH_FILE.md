# `STRATA_STATE_HASH_FILE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL verifier の各 decode window の実行前に GPU queue を待ち、ホストから読める GDN recurrent/conv state と、条件を満たす QSA int8 K/V state の FNV-1a ハッシュを指定ファイルへ記録するデバッグ用フックである。SYCL 実装の `Verifier::run` だけにあり、CUDA/HIP の同名処理は確認できなかった。記録のための同期・読み戻し・ファイル I/O が加わるが、ここでの処理は state を書き換えない。`sycl/src/core/verify.cpp:174-183,2278-2295,2308-2336`。

## 値と判定

環境変数は `state_hash_file()` の関数内 `static` 初期化で一度読み、値全体を解釈せずパスとして `std::fopen(path, "w")` に渡す。`getenv` が null、または先頭文字が NUL（空文字）ならファイルを開かず無効になる。空白、`0`、`false` なども文字列としてそのままパスに使われ、真偽値としては判定されない。`"w"` で開くため、成功時には既存ファイルを切り詰める。`sycl/src/core/verify.cpp:178-183`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `state_hash_file()` 初回呼び出し | 無効（null pointer を static に保持） | 空でないパス文字列で、`fopen(path, "w")` が成功 | 空文字、またはパスを開けず `fopen` が null を返す |

パスの内容に対する数値変換、大小文字比較、空白除去、範囲制限、CLI 引数や別環境変数による上書きはない。`fopen` が失敗した場合は null が static に保存され、再試行も警告もない。書き込みと `fflush` の戻り値も検査されない。`sycl/src/core/verify.cpp:178-183,2308-2309,2334-2336`。

## 有効になる条件

- 実行ファイルに `sycl/src/core/verify.cpp` の SYCL verifier が組み込まれ、推論経路から `Verifier::run` が呼ばれること。同ファイルに OS 固有の条件分岐はない。生成経路の呼び出し例は `src/program/generate.cpp:10902,12375,13712`。
- 変数の読み取りは `Verifier::run` が最初に `state_hash_file()` を呼ぶ時点で行われる。未設定・空文字をその時点で読んだ場合、後から環境を設定しても有効にならない。最初の呼び出し前に設定されていればその値を使い、その後の変更は反映されない。`sycl/src/core/verify.cpp:178-183,2278-2279,2308`。
- ファイルが開けても、GDN の行は `ss.gdn_alloc` 個を走査するための GDN state がある場合に出力される。QSA の行は `ss.qsa_alloc` 内で `kv_int8` が真かつ `q.k_q` が非 null の state ごとに出力される。`sycl/src/core/verify.cpp:2310-2325`。
- `STRATA_STATE_DUMP` は独立した追加条件である。このハッシュ処理が有効な場合に限り、`STRATA_STATE_DUMP` が設定され、window 番号が 0 で、対象が最初の4つの GDN state なら、生 state を `<prefix>_gdn<N>.bin` に書く。`STRATA_STATE_DUMP` 単独ではこの箇所の raw dump は行われない。dump ファイルを開けない場合も専用ログはない。`sycl/src/core/verify.cpp:2315-2318`。

## 実行時の詳細

`Verifier::run` は capture と入力 staging の後、window の GPU 処理を起動する前にファイル有効性を確認する。有効な場合は `cs_->wait()` で queue を待ち、GDN state を host buffer にコピーしてハッシュを計算する。その後、既に埋まったページ数 `(pos0 + 3) / 4` 分について対象 QSA state の K/V int8 コードと scale を読み戻してハッシュ化する。各行は `<window番号> gdn <GDN ordinal> <16桁16進ハッシュ>` または `<window番号> qsa <QSA ordinal> <16桁16進ハッシュ>` の形式で、各 window の終わりに `fflush` する。GDN ハッシュは `gf * 4` バイトの state、QSA ハッシュは K、V、K scale、V scale の各データのハッシュを順に混合する。`sycl/src/core/verify.cpp:2308-2336`。

static `FILE*` はプロセス中保持され、明示的な close はこの処理にない。window ごとの queue wait と state 読み戻しによって実行時間や同期状態は変わる。ログ出力、state の書き換え、生成 token の選択をこのコードが行うことはない。SYCL 例外が `run` の処理中に発生すると、例外文と `Exception caught at file:` を stderr に出して `exit(1)` する。この例外経路は当該環境変数に固有のエラー処理ではない。`sycl/src/core/verify.cpp:2308-2336,2875-2879`。

## ログと測定値

この変数が有効になったことを示す専用ログはない。通常の記録先はハッシュ行を含むファイルである。open、`fprintf`、`fflush` の失敗を検査しておらず、失敗理由を示す Strata の警告・エラー文字列はない。性能測定値は Strata の資料に確認できなかった。

## 根拠

- `sycl/src/core/verify.cpp:174-183` — デバッグ用途の説明、環境取得、空値判定、static cache、ファイル open。
- `sycl/CMakeLists.txt:37` — SYCL build のソース一覧に verifier 実装を登録。
- `sycl/src/core/verify.cpp:2278-2295,2308-2336` — verifier window 内の呼び出し位置、queue wait、state の選別・ハッシュ・出力。
- `sycl/src/core/verify.cpp:2875-2879` — SYCL 例外時の stderr 出力と終了。
- `src/program/generate.cpp:10902,12375,13712` — 生成経路からの `Verifier::run` 呼び出し。
