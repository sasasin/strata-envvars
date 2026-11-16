# `STRATA_SYCL_ROUTING_AUDIT_FILE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の verifier が device-side expert plan を記録する診断用フックである。空でない環境値を出力先パスとして使い、計画内容を JSON Lines 形式で追記する。通常の推論経路の選択や token 生成を切り替える設定ではなく、監査記録の出力と、その前提条件検査を追加する。読み取り・実装は `sycl/src/core/verify.cpp` の `Verifier::init` と window 完了処理にある（`sycl/src/core/verify.cpp:555-557,907-912,2679-2722`）。

このコードは `STRATA_SYCL_WORKLOAD_TRACE` がコンパイル時に定義された場合にだけ含まれる。SYCL CMake の同オプションは既定で `OFF` で、`ON` の場合に `verify.cpp` へ `STRATA_SYCL_WORKLOAD_TRACE=1` を付ける（`sycl/CMakeLists.txt:31-44`）。この診断用ビルドでない実行ファイルでは、この環境変数を読むコードも監査出力処理もない。

## 値と判定

`Verifier::init` の呼び出しごとに `std::getenv` で値を読み、ポインターが非 null かつ先頭文字が NUL でない場合だけ有効とする。値全体の比較や数値変換はせず、文字列をそのまま `std::fopen(path, "a")` に渡す（`sycl/src/core/verify.cpp:102-112,907-912`）。空白除去、大文字小文字変換、パス形式の事前検証はない。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_SYCL_WORKLOAD_TRACE` 定義あり | 監査しない | `audit.jsonl`、`/tmp/audit.jsonl`（空でない任意の文字列） | 空文字列（監査しない） |
| `STRATA_SYCL_WORKLOAD_TRACE` 定義なし | 環境変数を読まず監査しない | なし | すべて（このコード経路自体が未コンパイル） |

`0`、`false`、`0anything` も空でないためパス名として有効であり、真偽値としては解釈されない。末尾や先頭の空白も値の一部としてパスに渡される。CLI 引数や設定ファイルによる同名値の上書きはこの実装にない。

## 有効になる条件

- 実行ファイルが SYCL backend でビルドされ、かつ CMake オプション `STRATA_SYCL_WORKLOAD_TRACE=ON` により該当コードがコンパイルされていること（`sycl/CMakeLists.txt:31-44`）。
- `STRATA_SYCL_ROUTING_AUDIT_FILE` が空でないこと（`sycl/src/core/verify.cpp:907-912`）。
- verifier の `device_plan_` が有効であること。設定時には `STRATA_VERIFY_DEVICE_PLAN` が設定済みかつ `std::atoi(value) != 0` であり、`all_resident_` と `always_publish_` がともに false である必要がある。したがって `STRATA_VERIFY_DEVICE_PLAN` 未設定・空文字・`0`・数値変換結果が 0 の文字列では計画は有効にならない。`atoi` は文字列全体の厳密な検証ではない（`sycl/src/core/verify.cpp:827-855`）。
- `all_resident_` の判定には `STRATA_VERIFY_ALL_RESIDENT` が関係する。`hits.h_res`、`hits.d_res`、`hits.cache_base` が揃った場合、同変数が未設定または `atoi` の結果が非 0 なら全 expert の常駐を確認し、全常駐なら `all_resident_` が true となって `device_plan_` は false になる（`sycl/src/core/verify.cpp:827-855`）。
- device plan 用の device allocation が失敗すると `device_plan_` は false に戻され、その後の監査設定で `routing audit requires device planning` を送出する（`sycl/src/core/verify.cpp:874-897,907-910`）。
- 監査対象の plan が完成した window では expert layout が `native` である必要がある。そうでなければ `routing audit requires native expert layout` を送出する（`sycl/src/core/verify.cpp:2679-2686`）。

## 実行時の詳細

環境変数は verifier 初期化時に読み取られ、各 verifier インスタンスの `routing_audits` マップに `RoutingAudit` を登録する。値は関数内 `static` に cache されないが、初期化後にプロセス環境を書き換えても、その verifier の出力先は変わらない。別 verifier の初期化では再度読み取る（`sycl/src/core/verify.cpp:907-912,121`）。

`RoutingAudit` はパスを `"a"` で開き、モデル層数・group 数に対応する host snapshot 領域を確保してゼロ初期化する。open に失敗すると `routing audit output unavailable`、領域確保に失敗すると `std::bad_alloc` を送出する（`sycl/src/core/verify.cpp:102-120`）。

各 layer/group の expert plan を queue 上で snapshot 領域へコピーし（`sycl/src/core/verify.cpp:1757-1760`）、window 完了時に plan の整合性を検査して `kind` が `expert_plan` の JSON object を一行ずつ出力する。記録項目には `raw_ns`, `position`, `T`, `layer`, `group`, `rows`, `GU_type`, `down_type`, geometry/row-byte 情報、plan group と entry 数、各 group の `count`, allocation 種別、pointer、`dst` と `tok` 配列が含まれる。各 window の出力後に `fflush` する（`sycl/src/core/verify.cpp:2679-2722`）。

監査値の不整合は `routing audit: incomplete resident plan`、`routing audit: invalid group range`、`routing audit: invalid entry mapping`、`routing audit: missing entry` の例外となる（`sycl/src/core/verify.cpp:2692-2719`）。`Verifier::init` は SYCL exception だけを catch し、そこでの監査 `std::runtime_error` は `err` 文字列へ変換されない（`sycl/src/core/verify.cpp:555-557,907-925`）。このため、通常の `init` が false を返した際に呼び出し元が行う起動拒否ログの経路とは異なる（例: `sycl/src/program/generate.cpp:13357-13360`）。この関数は `fprintf` / `fflush` の戻り値を検査していないため、書き込み失敗時の追加処理は確認できない。

Verifier の破棄時に map entry を消し、`RoutingAudit` の destructor が snapshot を解放して出力ファイルを閉じる（`sycl/src/core/verify.cpp:502-524,115-118`）。

## ログと測定値

成功した監査について、この変数専用の stdout/stderr ログはない。指定ファイルに JSON Lines が追記される。出力ファイルを開けない場合や device planning が無効な場合の例外メッセージは上記のとおりで、Strata ソースにこの環境変数についての測定値はない（`sycl/src/core/verify.cpp:107-112,907-910,2697-2722`）。

## 根拠

- `sycl/CMakeLists.txt:31-44` — 診断ビルド option の既定値と macro 定義。
- `sycl/src/core/verify.cpp:102-121` — 出力先を追記モードで開く処理、snapshot と map。
- `sycl/src/core/verify.cpp:827-897` — 全常駐判定、device plan の条件と allocation fallback。
- `sycl/src/core/verify.cpp:907-912` — 環境値の唯一の読み取りと初期化時の検査。
- `sycl/src/core/verify.cpp:1757-1760,2679-2722` — plan snapshot、JSONL 出力、整合性検査と flush。
- `sycl/src/core/verify.cpp:502-524,555-557,922-925` — cleanup と init の例外処理。
- `sycl/src/program/generate.cpp:13357-13360` — 通常の init 拒否時に呼び出し元が出すログ。
