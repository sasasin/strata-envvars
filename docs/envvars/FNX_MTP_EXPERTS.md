# `FNX_MTP_EXPERTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の Flash-Next MTP draft layer が読む expert 重みファイルの形式を選びます。`q2_0` は runtime directory の `experts.bin` を読み、内部で Q4_0 ブロックへ展開します。`q4_0` は `experts-q4_0.bin` を読みます。いずれも MTP layer の expert gate/up/down の入力を選ぶもので、通常の Strata engine の設定ではありません。候補一覧には載っていますが、Strata ソースで環境から値を読む実装は `src/split/src/model.cpp` の `MtpFiles` にある 1 箇所だけです。`docs/DETAILS.md` にこの環境変数の説明や測定値はありません。

## 値と判定

| 値 | 判定と動作 |
|---|---|
| 未設定 | `q2_0` を既定値にして `experts.bin` を読む。 |
| `q2_0` | `experts.bin` を読み、Q2_0 のコードとスケールから Q4_0 ブロックを構成する。 |
| `q4_0` | `experts-q4_0.bin` を読み、Q4_0 ブロックとして扱う。 |
| 空文字、または上記以外 | 受理しない。`mtp: FNX_MTP_EXPERTS=<値>: q2_0 or q4_0` の例外になる。 |

値は `std::string` との完全一致で比較されます。大文字小文字の変換、空白除去、数値変換、部分一致はありません。したがって `Q2_0`、`q2_0 `、`1` は無効です。CLI 引数による形式の上書きや、別環境変数との優先順位もありません。`--mtp` は runtime directory を指定しますが、expert 形式はこの変数で別途選びます。

## 有効になる条件

- `strata-split` は `STRATA_BUILD_SPLIT=ON` のときだけ追加される opt-in target で、CMake の条件上 Linux の CUDA または HIP ビルドが対象です（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:20-30`）。通常の Strata engine にはこの読取箇所はありません。
- `sfnx` は `--serve`、`--native`、`--mtp` を要求し、モデルと MTP layer を初期化するときに `Mtp` を構築します（`src/split/tools/sfnx.cpp:72-104,1040-1061`）。この Flash-Next 向け構築経路で `MtpFiles` が作られます（`src/split/src/model.cpp:1193-1227`）。
- `FNX_27B` の分岐では MTP draft layer はモデル内蔵として処理され、`MtpFiles` を使いません（`src/split/src/model.cpp:1142-1192`）。ただし `strata-split` の現行 CMake target は `FNX_27B=0` でコンパイルされます（`src/split/CMakeLists.txt:102,113`）。
- 指定したファイルが存在しない、または形式に合わない場合は、この変数の判定後のファイル読込で失敗します。環境変数自体にファイル存在確認や別形式への fallback はありません。

## 実行時の詳細

`MtpFiles` の構築時に `std::getenv("FNX_MTP_EXPERTS")` を一度呼び、未設定なら `q2_0`、設定されていればその文字列をそのまま判定します。グローバル/static cache はなく、`MtpFiles` を新たに構築すればその時点の環境値を読みます。通常の `sfnx` 起動では MTP 初期化時の読取であり、以後のリクエストごとには読みません（`src/split/src/model.cpp:913-951,1193-1227`）。

`q2_0` の場合、`experts.bin` の各 expert のコードとスケールを走査し、Q4_0 表現の gate/up/down バッファを作ります（`src/split/src/model.cpp:959-1007`）。`q4_0` の場合は `experts-q4_0.bin` の gate/up/down の各領域を読み、想定サイズと EOF を確認します（`src/split/src/model.cpp:1008-1021`）。両経路とも `MtpFiles::views()` が expert tensor を `etype` で構成し、MTP card 読込で gate/up/down を使います（`src/split/src/model.cpp:1023-1040,1122-1123`）。選択した値は成功時に stderr へ `fnx: draft layer experts <値>` と出ます（同 `:945-951`）。

不正値はコンストラクタから例外となります。`sfnx` は初期化例外を stdout の `ERR ...` と stderr の `sfnx: failed: ...` に出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1052-1062`）。有効値でも、該当するファイルが開けなければ `mtp: cannot open ...`、サイズ不一致等では対応する `mtp:` エラーになります（`src/split/src/model.cpp:914-921,971-997,1015-1021`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:550`。候補名の全参照を `rg -n --hidden --glob '!.git/**' 'FNX_MTP_EXPERTS'` で確認し、実際の環境読取は以下の `std::getenv` 1 箇所、他は同じ行周辺のコメントのみでした。
- 値の既定、分岐、無効値、成功ログ: `src/split/src/model.cpp:942-951`。
- `q2_0` の変換と `q4_0` ファイルの読込・検査: `src/split/src/model.cpp:959-1021`。
- MTP tensor の作成と配置: `src/split/src/model.cpp:1023-1040,1122-1123,1193-1227`。
- `strata-split` の build 条件: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:20-30,102,113`。
- CLI 起動条件と初期化失敗の観測結果: `src/split/tools/sfnx.cpp:72-104,1027-1035,1040-1062`。
