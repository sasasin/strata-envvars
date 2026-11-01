# `STRATA_DS4_SLOT_CAP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 用 `maya-ds4 --serve` エンジンの会話 slot 機能で、RAM に保持する退避会話の最大数を指定します。slot は別の会話へ切り替える際にモデル状態を保存し、後の prompt で取り戻す仕組みです。上限を超えたときは RAM 内の least-recently-used slot を slot フォルダーへ書き出します。これはディスク上の総 slot 数を制限する値ではありません。

## 値と判定

値の取得は `env_num` lambda が `std::getenv` と `std::atof` を使って行います。環境変数が未設定なら既定値 `4` です。設定されていれば `atof` の結果を `int` に変換し、その後 `std::max(0, ...)` で負値を 0 にします。

| 入力 | 判定結果 |
|---|---|
| 未設定 | 4 |
| 空文字、または数値として読めない文字列 | `atof` が 0 を返すため 0。slot は無効 |
| 数値文字列 | 数値を `int` に変換（小数部は 0 方向へ切り捨て）、0 未満なら 0 に clamp |
| 例: `3.9`, `3tail` | それぞれ 3。`atof` は整数専用 parser ではなく、数値 prefix を読み、末尾全体の妥当性を検査しない |
| 例: `-2`, `0`, `0.9` | いずれも 0。slot は無効 |

整数で表現できないほど大きい有限値や NaN / infinity を `int` に変換した場合の結果は、C++ の浮動小数点から整数への変換規則上、定義された有効な設定値として扱えません。明示的な入力検査やエラー報告はありません。

ただし、この値を読むのは先に `STRATA_DS4_SLOT_KEEP` が設定済みかつ `atoi(value) != 0` の場合だけです。`STRATA_DS4_SLOT_KEEP` が未設定または `atoi` 結果が 0 のとき、slot cap は環境から読まれず `slot_max` は 0 になり、slot 機能全体が無効になります。

## 有効になる条件

- 読み取り箇所は `src/dsv41/ds4_main.cpp` の `serve()` 内です。通常の `--ids` 等の一回実行、`--pack-info` ではこの値を読みません。
- `--serve` でエンジンを起動し、かつ `STRATA_DS4_SLOT_KEEP` が有効で、slot cap が 1 以上である必要があります。
- CLI に slot cap を指定する引数はありません。モデル読み込み後に `serve()` が環境を読み、同じ `serve()` 実行中は `slot_max` を保持します。
- slot 機能の初期化時に slot フォルダーがディレクトリーとして利用できない場合、stderr に `ds4 slots: <path> is not writable - conversations are not set aside` を出し、`slot_max` を 0 にして機能を無効化します。
- Python サーバーの `child_env()` は親環境をコピーし、その後設定ファイルの `env` を反映します。DeepSeek-V4.1 用設定は `STRATA_DS4_SLOT_KEEP` と `STRATA_DS4_SLOT_GB` を `setdefault` で補いますが、`STRATA_DS4_SLOT_CAP` は変更しません。したがって通常は親環境の cap 値が継承され、設定ファイルの `env` に同名キーがあればその値が優先されます。

## 実行時の詳細

上限超過の判定は、新しい会話状態を slot に保存した後、RAM slot 数を数え `ram <= slot_max` になるまで繰り返します。超過していると最も古く使われた RAM slot をファイルへ書き出し、書き出せなければその slot を破棄します。既存のディスク slot は起動時に slot 一覧へ読み込まれますが、`slot_max` が数えるのは `data` が RAM にある slot だけです。従って cap はディスク保存分を含む総会話数ではありません。

slot が無効（cap 0 以下を含む）なら、会話の退避・復元、起動時の slot フォルダー読み込み、終了時の RAM slot 書き出しを行いません。有効時でも slot 状態の保存・復元失敗や会話長の条件により退避・再利用されない経路があります。cap の値自体については、専用のログ、警告、終了コードはありません。slot が保存・取り戻しされたときの `NOTE sessions: ...` stdout 通知と `ds4 slots: ...` stderr 出力は、その後の操作結果を示します。

値は `serve()` 開始時に一度評価され、リクエストごとには再読込しません。エンジンプロセス起動後に環境を変更しても反映されません。Python サーバーからは `env` を渡して子プロセスを起動します。

## 根拠

- `src/dsv41/ds4_main.cpp:388-390,416-423`: `serve()` 内の読み取り、`atof`、既定値 4、`KEEP` による条件付き評価。
- `src/dsv41/ds4_main.cpp:547-576`: cap が 0 以下のときの無効化と、RAM slot 数が cap を超えた場合の LRU 書き出し／失敗時破棄。
- `src/dsv41/ds4_main.cpp:647-655,699-704`: 有効時のフォルダー読み込み、利用不可時の stderr 通知と機能停止。
- `src/dsv41/ds4_main.cpp:1025-1048`: エンジン終了時の RAM slot 書き出しと結果通知。
- `src/dsv41/ds4_main.cpp:1284-1410`: `--serve` の CLI 判定とモデル読み込み後の `serve()` 呼び出し。slot cap 用 CLI 引数はありません。
- `serve/server.py:3747-3764`: 子環境の親環境コピー、config `env` の上書き、DeepSeek slot 設定。
- `serve/server.py:3653-3667,1077-1079`: サーバーが `KEEP` / `GB` を補い、エンジン子プロセスへ環境を渡す処理。`SLOT_CAP` は設定されません。
