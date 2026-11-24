# `INK_LOGITS_HASH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling` の直接 CLI 生成で、各生成段階の logits 配列を FNV-1a 風の 64-bit ハッシュにして stderr へ出す診断用スイッチです。logits の計算・サンプリング・標準出力の token 列はこの分岐では変更しません。実装は `engine/src/inkling2/ink_main.cpp` の直接生成経路にあります（同ファイル:1097-1146）。

このコードは `strata-inkling` ターゲットの `ink_main.cpp` に含まれます。エンジン側で `STRATA_BUILD_INKLING` と `STRATA_BUILD_INKLING2` がともに有効なときに `inkling2` サブディレクトリを追加します（`engine/CMakeLists.txt:1000-1005`、`engine/src/inkling2/CMakeLists.txt:176-180`）。

## 値と判定

環境から `std::getenv("INK_LOGITS_HASH")` を読み、値が存在し、かつ先頭文字が `'1'` である場合だけ有効です。文字列全体の比較や数値変換はしません（`engine/src/inkling2/ink_main.cpp:1122-1123`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `strata-inkling` の直接 CLI 生成経路 | 無効 | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1` |

大文字小文字や空白の正規化はなく、先頭が文字 `'1'` かどうかだけを見ます。したがって `01` や `+1` も無効です。CLI 引数・設定ファイル・別環境変数による上書きはありません（同ファイル:1122-1123）。

## 有効になる条件

- `strata-inkling` がビルドされている必要があります。ビルド時に Inkling ターゲット自体が除外されていれば、この読み取り箇所は実行されません（`engine/CMakeLists.txt:1000-1005`）。
- `--serve` はモデルと backend の初期化後に `run_serve_loop` へ進み、直接 CLI 用のハッシュ処理を通りません（`engine/src/inkling2/ink_main.cpp:1093-1097`）。
- `--bench`、`--info`、`--selfcheck`、その他の早期終了する診断経路も、直接生成部へ進まないため対象外です（`engine/src/inkling2/ink_main.cpp:1039-1071`）。
- 直接生成経路でモデルを開き backend を初期化し、slot を確保して最初の `forward_batch` に成功した後で初めて値を読みます。これらの前段で失敗すればハッシュ行は出ません（同ファイル:1078-1115）。
- CPU/GPU の選択や backend をこの変数が切り替える処理はありません。ビルドされた同一の `ink_main.cpp` 直接生成経路での診断出力を制御します。

## 実行時の詳細

環境値は prompt の最初の `forward_batch` が成功した後、直接生成処理に入った時点で読みます。結果はローカル `const bool hash_logits` に一度だけ保持され、生成ループ中に再読込しません（`engine/src/inkling2/ink_main.cpp:1113-1125`）。そのため、この読み取り後にプロセス環境を書き換えても現在の生成には反映されません。

有効時は初期 logits に対して `step -1` を1行出します。各 token を出力した後、EOS/EOT でなければ次の logits を計算し、その成功後に `step 0` 以降の行を出します。EOS/EOT token の後には次の forward がなく、その token に対応する追加ハッシュ行もありません（`engine/src/inkling2/ink_main.cpp:1124-1145`）。

ハッシュ対象は `logits.data()` の `logits.size() * sizeof(float)` バイトで、初期値 `1469598103934665603ull` から各 byte を XOR し、`1099511628211ull` を乗算します。標準出力の token 列は既存どおり `printf` で出し、ハッシュは stderr に `[logits-hash] step %d %016llx\n` の形式で出します。ハッシュ行は計算済みの値を観測するだけで、次の生成処理には渡されません（同ファイル:1124-1145）。

## ログと測定値

有効時の stderr 行は `[logits-hash] step %d %016llx` です（改行付き、`engine/src/inkling2/ink_main.cpp:1129`）。無効時はハッシュ関数が直ちに戻り、ハッシュ行を出しません（同ファイル:1124-1125）。この commit の `docs/DETAILS.md` は存在せず、この変数に関する測定値も確認できませんでした。

## 根拠

- `engine/src/inkling2/ink_main.cpp:1078-1115` — モデル/backend 初期化、slot 確保、初回 forward と失敗経路。
- `engine/src/inkling2/ink_main.cpp:1093-1097` — serve 経路と直接 CLI 生成経路の分岐。
- `engine/src/inkling2/ink_main.cpp:1122-1145` — 環境値判定、ハッシュ計算・出力、生成ループとの位置関係。
- `engine/CMakeLists.txt:1000-1005`、`engine/src/inkling2/CMakeLists.txt:176-180` — Inkling ターゲットの条件と `ink_main.cpp` の登録。
