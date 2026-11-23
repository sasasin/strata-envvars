# `DEBUG_HIP_DYNAMIC_QUEUES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は Strata 内の計算分岐を選ぶためには parse されず、HIP の通常ビルドで HIP 初期化前に Strata が環境へ設定する値を制御する。利用者が `DEBUG_HIP_DYNAMIC_QUEUES` をすでに設定していれば値を問わずそのままにし、未設定なら通常は `0` を設定する。`STRATA_HIP_DYNAMIC_QUEUES` が文字 `1` で始まる場合は `DEBUG_HIP_DYNAMIC_QUEUES` を設定せず、HIP runtime の既定値を保つ経路になる。対象箇所は engine の `main`（Windows HIP では `engine_main`）内である。`engine/src/program/generate.cpp:3662-3666,3816-3831`。

## 値と判定

`DEBUG_HIP_DYNAMIC_QUEUES` は `std::getenv(...) == nullptr` かどうかだけで確認し、値の文字列自体は読み取らない。したがって空文字を含む、環境に存在する値はすべて明示設定として優先され、Strata は変更しない。変数が未設定のときだけ `STRATA_HIP_DYNAMIC_QUEUES` を確認し、その先頭 1 文字が `'1'` かで判定する。後者も文字列全体の parse、空白除去、大文字小文字変換、数値検証はしない。`engine/src/program/generate.cpp:3821-3828`。

| ビルド・環境 | `DEBUG_HIP_DYNAMIC_QUEUES` 未設定時 | 設定済み時に Strata がすること |
|---|---|---|
| `STRATA_USE_HIP` かつ `STRATA_HIP_GFX906` ではないビルド | `STRATA_HIP_DYNAMIC_QUEUES` が先頭 `'1'` なら何も設定しない。それ以外（未設定・空文字を含む）は `DEBUG_HIP_DYNAMIC_QUEUES=0` を設定する | 値が空文字、`0`、`1`、その他のどれでも変更しない |
| それ以外のビルド | このコードによる処理なし | このコードによる処理なし |

たとえば `DEBUG_HIP_DYNAMIC_QUEUES=` は「設定済み」なので保たれる一方、未設定かつ `STRATA_HIP_DYNAMIC_QUEUES=1anything` は先頭文字が `1` のため Strata は上書き値を設定しない。`STRATA_HIP_DYNAMIC_QUEUES=true`、` 1`、`0`、空文字は `1` で始まらず、未設定時には `DEBUG_HIP_DYNAMIC_QUEUES=0` を設定する。`engine/src/program/generate.cpp:3821-3828`。

## 有効になる条件

- 処理は `STRATA_USE_HIP` が定義され、かつ gfx906 互換ビルドを示す `STRATA_HIP_GFX906` が未定義の実行ファイルに限られる。OS 条件はなく、Windows とそれ以外で環境変数を書き込む API だけが分かれる。CMake は gfx906 互換ビルドと wave32 HIP ビルドを別 backend としている。`engine/src/program/generate.cpp:3816-3828`; `engine/CMakeLists.txt:92-104`。
- `DEBUG_HIP_DYNAMIC_QUEUES` の環境エントリーが既にあると、値が空でも `STRATA_HIP_DYNAMIC_QUEUES` は見ず、既存値を優先する。
- 既存値がなくても、`STRATA_HIP_DYNAMIC_QUEUES` が文字 `'1'` で始まれば Strata は `DEBUG_HIP_DYNAMIC_QUEUES` を追加しない。これは Strata が runtime 既定値を保つ設定経路であり、Strata 内で `DEBUG_HIP_DYNAMIC_QUEUES` の値を別途解釈する経路は確認できない。`engine/src/program/generate.cpp:3820-3828`。
- `STRATA_USE_HIP` が未定義、または `STRATA_HIP_GFX906` が定義されたビルドでは、この処理自体がコンパイル対象外である。`engine/src/program/generate.cpp:3816-3832`。

## 実行時の詳細

通常の engine 起動時、オプション解析より前に一度だけ両環境変数を参照し、必要なら現在のプロセス環境に `DEBUG_HIP_DYNAMIC_QUEUES=0` を設定する。その直後に `prime_hw_queues()` を呼ぶ。ソースコメントは設定が最初の HIP API 呼び出しより前に必要としている。値を static cache したり、生成リクエストごとに再読したりする処理ではない。プロセス起動後に環境を外部から変えても、この分岐が再評価されることはない。設定関数の戻り値は検査されない。`engine/src/program/generate.cpp:3816-3832`。

`--version`、`--families`、`--geometry`、`--expert-support` はこの処理より前に返るため、これらの早期終了経路では環境値を変更しない。その他の CLI 引数による上書きはない。`engine/src/program/generate.cpp:3696-3735,3816-3832`。この箇所から別プロセスへの転送や子プロセス環境の設定は確認できない。

## ログと測定値

この環境変数の確認・設定自体はログを出さず、設定失敗も報告しない。ソースコメントは ROCm/TheRock の dynamic queue assignment に起因するコピー／計算キューの重なりや停止を避ける動機を記しているが、この文書では HIP runtime や driver の内部動作・性能を Strata の挙動として扱わない。`engine/src/program/generate.cpp:3817-3831`。

## 根拠

- `engine/src/program/generate.cpp:3816-3832` — build 条件、値の有無判定、`STRATA_HIP_DYNAMIC_QUEUES` の先頭文字判定、OS ごとの設定、`prime_hw_queues()` より前の適用。
- `engine/src/program/generate.cpp:3662-3666,3696-3735` — engine の入口と環境設定より前に終了する CLI 経路。
- `engine/CMakeLists.txt:92-104` — gfx906 互換 backend と wave32 HIP backend の区別。
