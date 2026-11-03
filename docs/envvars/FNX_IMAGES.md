# `FNX_IMAGES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`FNX_IMAGES` は split engine の同梱診断ツール `fnx_run` が `logits` モードで使う画像埋め込みファイル（`.sve`）のパスです。ファイル内の画像レコードを読み、prompt 中の image-pad token を画像セル用 token に置き換えて `Engine::set_images()` に渡します。通常の `strata` CLI や sFNX サーバーがこの名前を読む箇所は確認できません。

この読み取りは `split_fnx_run` ターゲットにあり、CMake の `STRATA_BUILD_TESTS` が有効で、split engine が利用可能な Linux CUDA/HIP ビルドで作られるテスト・診断用 executable です。`fnx_run.cpp` は CUDA 言語としてコンパイルされます（`src/split/CMakeLists.txt:20-30,64-80,126-165`）。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 画像ファイルを開かず、`FNX_IMAGES` による `set_images()` も行わない。 |
| 設定あり | 空文字を含め、値全体をファイルパスとして `fopen(value, "rb")` に渡す。数値化、trim、拡張子検査、別の既定パスへの fallback はない。 |
| 空文字または開けないパス | `perror(value)` を stderr に出し、`run_logits()` は 1 を返す。 |

読み込むレコードは5個の32-bit header 値と `h[1] * fnx::N` 個の float 値からなります。Strata は header の magic が `0x31455653` であることと `h[4] == fnx::N`（埋め込み幅）を検査し、違えば `"<path>: not strata-vision records of width <N>"` を stderr に出して 1 を返します。payload が指定数に満たない場合も 1 を返しますが、その分岐に専用メッセージはありません。header の `h[1]`, `h[2]`, `h[3]` の正数性や相互関係をこの読み取り箇所は検査しません（`src/split/tools/fnx_run.cpp:129-141`）。

ファイルの画像レコードは prompt 中の image-pad token の出現順に割り当てられます。prompt 内の画像数がレコード数より多い場合は `more images in the prompt than in <path>` を stderr に出して 1 を返します。prompt より余ったレコードを拒否する処理はありません（同: `142-153`）。

## 有効になる条件

- `fnx_run` の `logits PROMPT.bin CONT.lgr T OUT.lgr` モードでのみ、直接 `run_logits()` の画像処理を通ります。`fnx_run_cmd()` はモデルと engine を作った後にこのモードを選択します（`src/split/tools/fnx_run.cpp:958-993,1364-1373`）。
- 値が設定されていても、prompt に image-pad token がなければ画像レコードは `imgs` に割り当てられず、画像数 0 の `logits: 0 image(s)` が出ます。prompt に画像があれば、各 image-pad token run に対応するレコードが必要です（同: `142-153`）。
- CLI に `FNX_IMAGES` を指定する引数はありません。`logits` の prompt/reference/output 等の引数や `FNX_PREFILL` は別用途で、画像ファイルパスを上書きしません（同: `958-993`）。
- `exact` モードも内部で `run_logits()` を呼びますが、画像 prompt を処理する直前に `FNX_IMAGES` を `ref/img/sphinx.sve`（`FNX_27B` build ではモデル別 `pic_stem + ".sve"`）へ設定し、その後 `unsetenv()` します。したがってその画像比較では呼び出し元の値は使われず、元の値を保存・復元する処理もありません（同: `746-764,877-887`）。
- `FNX_IMAGES` 自体は `run_logits()` のたびに読み取られ、static cache はありません。`exact` の画像経路は各呼び出しで一時的に値を設定・解除します（同: `129,877-887`）。

## 実行時の詳細

`logits` モードでは `.lgr` reference と出力ファイルを開いた後、prompt token 列のコピーを `feed` として作り、`FNX_IMAGES` が設定されている場合に画像データを読み込みます。各 image-pad token run を `Engine::IMAGE_TOK` 系の ID に置き換え、画像の開始位置・cell 数・grid・埋め込み行ポインタを `Engine::Image` にまとめて `e.set_images(imgs)` に渡します。その直後に stderr へ `logits: <枚数> image(s)` を出し、以後の prefill/window 計算に `feed` を使います（`src/split/tools/fnx_run.cpp:124-153,155-168`）。

環境変数の読み取りは `run_logits()` 呼び出しごとの処理で、値を保存する cache はありません。プロセス起動後に環境が変われば、後続の呼び出しは新しい値を読みます。ただし独立した `fnx_run` は通常1コマンドで終了します。`exact` は画像比較用にプロセス環境を一時変更し、元の値があっても処理後に unset します（同: `129,877-887`）。

ファイルを開けない、認識しない header、payload 不足、prompt の画像数超過は `run_logits()` から 1 で戻ります。`fnx_run` の最上位 `main()` は例外を `fnx_run: <内容>` と stderr に出して終了コード 1 にしますが、上記の明示的な return 1 は例外経路ではなく、そのままプロセス終了コードになります（同: `129-145,1364-1373`）。正常時、画像ファイルを設定した経路では画像枚数と prompt token/step 数などが stderr に出ます（同: `152-153,175-184`）。

## 根拠

- `src/split/tools/fnx_run.cpp:124-153` — 環境からの読み取り、`.sve` open/header/payload 処理、prompt token の置換、`set_images()`。
- `src/split/tools/fnx_run.cpp:958-993,1364-1373` — `logits` CLI モードからの呼び出しと終了経路。
- `src/split/tools/fnx_run.cpp:877-887` — `exact` の画像比較時に固定パスを設定し、処理後に環境変数を解除する経路。
- `src/split/CMakeLists.txt:20-30,64-80,126-165` — split engine の platform/backend 条件と `STRATA_BUILD_TESTS` 配下の `split_fnx_run` 定義。
