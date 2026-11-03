# `FNX_EXACT_REF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`sFNX` の検証用実行ファイル `split_fnx_run` で `exact` モードを実行するとき、`long64` の llama.cpp 参照ログ `.lgr` を指定するための変数です。モデルの推論設定ではなく、計算結果を比較する試験用の参照ファイル選択に使われます。対象コードは Strata 本体の通常の起動経路ではなく、`STRATA_BUILD_SPLIT` で有効化される split engine の test driver です（`CMakeLists.txt:2947-2949`, `src/split/CMakeLists.txt:153-164`）。

`exact` は `long64`、`code1`、`edit1`、`picture` の各結果を参照と比較しますが、この変数が選択を変えるのは `long64` の参照だけです。値が指定されると、モデル名・Q4/Q8 区分・YaRN 用の既定パスより先にその値を参照パスとして使います（`src/split/tools/fnx_run.cpp:812-856`）。

## 値と判定

値は文字列として取得され、数値変換、トリム、形式検証は行われません。設定有無は `std::getenv()` の null 判定です。

| 状態 | `long64` の処理 |
|---|---|
| 未設定 | 通常のモデル・量子化・rope scale に基づく参照パスを選択する。Q8_0 では長文参照がない前提で比較をスキップする。 |
| 空文字で設定 | 設定済みとして扱う。Q8_0 のスキップを通過し、空のパスを参照ファイルとして開こうとするため、通常は参照ファイルなしの失敗になる。 |
| 非空文字列 | 文字列全体をファイルパスとして使い、そのファイルをバイナリ読み込みで開く。相対パスはプロセスの作業ディレクトリ基準。 |

`FNX_EXACT_REF` のパス指定は `long64` に限られます。`code1`、`edit1`、`picture` は従来の分岐で参照ファイルを選びます。CLI の `exact [NAME]` に渡す `NAME` は出力名であり、この環境変数の優先順位を変えません（`src/split/tools/fnx_run.cpp:765-770,812-856,958-981`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT` は既定で OFF です。split の CMake 構成が対象 OS/backend と GGML checkout の条件を満たし、さらに `STRATA_BUILD_TESTS` が ON で `split_fnx_run` ターゲットが作られている必要があります（`CMakeLists.txt:2947-2949`, `src/split/CMakeLists.txt:20-30,125-127,153-166`）。
- 実行モードが `exact` の場合にだけ参照選択に使われます。通常の Strata CLI やサーバーのモデル実行にはこの読み取り箇所はありません（`src/split/tools/fnx_run.cpp:958-981`）。
- `long64` は全モデルで環境変数による参照パス置換の対象です。ただし Q8_0 は変数が未設定なら先に比較をスキップします。空文字を含め、値が設定されていればこのスキップ条件を通過します（`src/split/tools/fnx_run.cpp:812-823,847-856`）。
- `FNX_ROPE_SCALE` が設定されている場合も `long64` の参照パスは `FNX_EXACT_REF` が優先されます。一方、rope scale 自体の扱いや比較基準は別途その値に従います（`src/split/tools/fnx_run.cpp:831-856,905-913`）。

## 実行時の詳細

`exact` の検証ループで `long64` に到達したときに `getenv()` を確認し、参照パスを選択します。結果を `static` や別のキャッシュに保存しません。選択したパスをまず `fopen(..., "rb")` で確認し、その後、生成した logits とともに `.lgr` として読み込み比較します（`src/split/tools/fnx_run.cpp:812-857,896-913`）。

選択したファイルが開けない場合は stderr に `exact: no llama.cpp reference <path> for <model>; make it with` と生成コマンドを表示し、stdout に `exact <name> long64: FAIL: no llama.cpp reference <path>` を出して終了コードを失敗状態にします（`src/split/tools/fnx_run.cpp:857-874`）。開けても `.lgr` が短い、または形式不正なら例外になり、実行ファイルの `main` が stderr に `fnx_run: <path>: a short or malformed .lgr file` 相当を出して `1` を返します（`src/split/tools/fnx_run.cpp:207-228,1364-1373`）。

## 根拠

- 候補名の全参照: `src/split/tools/fnx_run.cpp:746-748`（説明コメント）、`src/split/tools/fnx_run.cpp:820-823,847-856`（環境からの値取得と参照パス選択）。他の Strata ファイルに完全一致の参照はありません。
- ビルド条件と用途: `CMakeLists.txt:2947-2949`, `src/split/CMakeLists.txt:20-30,125-127,153-166`。
- `exact` の呼び出しと CLI: `src/split/tools/fnx_run.cpp:958-981,1364-1373`。
- ファイルの読込・不正形式の扱い: `src/split/tools/fnx_run.cpp:207-228,857-874,896-913`。
