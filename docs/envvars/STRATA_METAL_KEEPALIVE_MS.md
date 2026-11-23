# `STRATA_METAL_KEEPALIVE_MS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal runtime の `mtl::Context` がアイドル中に GPU keep-alive 用コマンドバッファを送る間隔を、ミリ秒で指定する。正数なら専用スレッドが短い Metal compute job を周期的に送信し、コンテキストが追跡する Metal buffer を job から参照する。0 以下ならスレッドを開始しない。これは `engine/metal/src/mtl_rt.mm` の `Context::Impl::start_keepalive()` に実装されており、Metal エンジンはモデルを開いた後に `mtl::Context` を作る経路で利用する（`engine/metal/src/mtl_rt.mm:76-119,139-148`、`engine/metal/src/engine/window.cpp:736-739`）。

## 値と判定

`std::getenv` で値を取得し、未設定または空文字列なら `250.0` を使う。それ以外は `std::atof` で数値変換し、変換結果が `ms > 0` の場合だけ処理を続ける。`atof` は文字列全体の妥当性を検証しないため、数値接頭部の後ろに文字があっても接頭部が使われ、数値に変換できない文字列は 0 となる。大文字小文字を使う真偽値判定はない。正数の上限や clamp はない（`engine/metal/src/mtl_rt.mm:76-82`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `mtl::Context` の生成時 | 250 ms | `1`, `0.5`, `1tail` など、`atof` の結果が正数 | 空文字は unset と同じ。`0`, `0tail`, `-1`, `false`, `abc` は 0 以下となり無効 |

先頭の空白や符号を含む数値も `atof` の変換規則に従う。`NaN` は `ms > 0` を満たさず無効。正数は待ち時間を `(ms * 1000)` microseconds に変換して `sleep_for` に渡すため、1 ms 未満の値も受理されるが microseconds 未満の端数は整数変換で切り捨てられる（`engine/metal/src/mtl_rt.mm:94-99`）。

## 有効になる条件

- macOS 専用の Metal build が対象。`engine/metal/CMakeLists.txt` は Apple 以外で configure を失敗させる。Metal 以外の backend にこの読み取りはない（`engine/metal/CMakeLists.txt:1-20`）。
- Metal runtime の `mtl::Context` が生成されること。Metal engine はモデルを開いた後に生成する。Metal device がない場合は keep-alive の評価前に `mtl: no Metal device` を stderr に出して終了コード 2 となる（`engine/metal/src/engine/window.cpp:736-739`、`engine/metal/src/mtl_rt.mm:139-148`）。
- この変数に対応する CLI 引数、設定ファイル優先順位、または build macro 分岐はない。間隔と実行時間窓は環境変数で決まり、窓は `STRATA_METAL_KEEPALIVE_WINDOW_S`（既定 120 秒）で別途指定される。同変数も unset / 空なら既定値、非空なら `atof`、結果が正数でなければ keep-alive を開始しない（`engine/metal/src/mtl_rt.mm:78-82`）。
- 初期化時の Metal keep-alive kernel または 256-byte shared buffer の作成に失敗すると機能は有効にならず、stderr に `mtl: the GPU keep-alive kernel did not build; keep-alive off` を出して戻る（`engine/metal/src/mtl_rt.mm:84-92`）。

## 実行時の詳細

値は `Context` のコンストラクタから `start_keepalive()` が呼ばれた時に一度読み取られ、`ms` と `win` は起動したスレッドへ値コピーされる。プロセス実行中に環境変数を変更しても既存コンテキストには反映されない。コンテキスト生成時に interval が正数でなければ窓の環境変数も読み取らず終了する（`engine/metal/src/mtl_rt.mm:76-82,139-148`）。

スレッドは interval ごとに待ち、最後の `touch()` から少なくとも interval が経過し、経過時間が window 以下で、macOS の `kern.memorystatus_vm_pressure_level` が正常より高いと判定されない場合に job を送る。sysctl の取得に失敗した場合も pressure 判定は false となる。job は追跡中の buffer を `useResource` で列挙してメイン command queue に commit し、完了を待つ。keep-alive 自身は `last_commit` を更新しない。window を過ぎた後は実行を止め、memory pressure が高い間も送信を見送る（`engine/metal/src/mtl_rt.mm:59-75,94-114`）。通常の Metal command buffer の commit では `touch()` が呼ばれ、基準時刻が更新される（同 `:437-455,459-484,488-500`）。

コンテキスト破棄時は停止フラグを立て、スレッドを join してから実装を破棄する（`engine/metal/src/mtl_rt.mm:153-156`）。この keep-alive job がモデル計算や生成結果を変える処理はコード上確認できない。Strata の説明コメントは、アイドル中に GPU allocation が解放されるまでの遅れを避ける目的と、window 経過または memory pressure 時に維持を止める設計を記している（`engine/metal/src/mtl_rt.mm:44-53`）。

## ログと測定値

値と window が正数で、kernel と buffer の初期化に成功すると stderr に `mtl: GPU keep-alive every %.0f ms for %.0f s after the last command buffer (#6078; STRATA_METAL_KEEPALIVE_MS=0 turns it off)` を出す（`engine/metal/src/mtl_rt.mm:117-118`）。値が無効、window が無効、または初期化失敗時はこの有効ログは出ない。初期化失敗時のログは「有効になる条件」を参照。コメント内の測定例は条件付きの観測記述であり、この調査では性能値として一般化しない（同 `:44-53`）。

## 根拠

- `engine/metal/src/mtl_rt.mm:44-53,76-119,139-156` — keep-alive の目的、環境変数の変換、条件、スレッド処理、ログ、開始と終了。
- `engine/metal/src/mtl_rt.mm:59-75,437-455,459-500` — idle 基準時刻の更新と pressure 判定。
- `engine/metal/src/engine/window.cpp:736-739` — Metal engine での `mtl::Context` 生成箇所。
- `engine/metal/CMakeLists.txt:1-20` — Metal build が macOS / Apple 専用であること。
