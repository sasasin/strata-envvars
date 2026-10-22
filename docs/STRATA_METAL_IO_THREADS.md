# `STRATA_METAL_IO_THREADS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンがモデルの routed expert を SSD から読み込むストリーミング経路で、expert I/O 用ワーカースレッド数を指定します。スレッドは arena の初期充填と、実行中に必要になる expert の読み込みを処理します。Metal エンジン以外の I/O スレッド数には作用しません。

## 値と判定

`ExpertStream::open()` がローカル helper `env_int()` で値を読みます。helper は変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を返します。その後 `std::max(1, ...)` が適用されます。

| 環境変数の値 | `nio_` |
|---|---:|
| 未設定、空文字 | 6 |
| `4` | 4 |
| `0`、`-3`、数値に変換できない文字列 | 1 |
| `3threads` | 3 |

`atoi` による整数変換なので、文字列全体の妥当性検査はありません。先頭の空白や符号の後にある整数部分を変換し、数字の後ろの文字は値の判定に使いません。変換結果が 1 未満なら 1 になります。正の値に対するコード上の上限はありません。根拠: `metal/src/engine/stream.cpp:27-30,149`。

## 有効になる条件

`STRATA_METAL_IO_THREADS` が読むのは `ExpertStream::open()` が呼ばれる場合だけです。Metal の `Window::init()` は GGUF を開き、対象モデルの geometry が Qwen3.8-Flash-Next の条件（48 layers など）に合った後、`ExpertStream::wanted()` でストリーミング要否を決めます。`STRATA_METAL_STREAM=1` なら有効、`=0` なら無効、それ以外（未設定を含む）はモデルが GPU working set に収まるかによる自動判定です。ストリーミングが選ばれない場合、この変数は読み取られず、全体を wrap する経路になります。根拠: `metal/src/engine/window.cpp:435-457`, `metal/src/engine/stream.cpp:33-48`。

I/O ワーカーは arena の作成時に `nio_` 本起動します。ストリーミングが選ばれても、arena の作成に至らない場合にはワーカーは起動しません。arena 作成は初期化後の実行経路から遅延して呼ばれます。根拠: `metal/src/engine/window.cpp:1143,1254-1257,1324-1329`, `metal/src/engine/stream.cpp:149,464-481`。

## 実行時の詳細

環境値は各 `ExpertStream::open()` 時に一度読み取られ、`nio_` に保存されます。プロセス実行中に環境を変更しても、既に作成済みの stream のスレッド数は変わりません。`make_arena()` は `nio_` 本の `io_main()` ワーカーを作成します。各ワーカーは queued job を取り出し、expert の読み込み片を `pread()` し、最後の片が終わると slot の状態を更新して待ち側へ通知します。初期 arena fill と後続の expert 読み込みが同じ I/O worker 群を使います。終了時は destructor が停止を通知し、全 worker を join します。根拠: `metal/src/engine/stream.cpp:50-58,272-333,335-346,464-482`。

値そのものを表示するログは見つかりません。streaming の起動状態は `strata metal: decode window ... streamed from the SSD (experts)` と表示され、実行後の `expert stream` 統計では読み込み数や待ち時間などが報告されますが、スレッド数は報告されません。根拠: `metal/src/engine/window.cpp:642-644`, `metal/src/engine/stream.cpp:803-821`。

## 文書・測定値との照合

`docs/MAC.md` は M4 上の SSD streaming について、read-ahead 深度、I/O threads、eviction order のそれぞれが decode に与えた差は 3% 未満と記載しています。これは複数の要因をまとめた記述で、`STRATA_METAL_IO_THREADS` 単独の値別測定や全機種での効果を示すものではありません。したがって、特定のスレッド数の性能優位はこの調査からは断定しません。根拠: `docs/MAC.md:145-157`。

## 根拠

- `metal/src/engine/stream.cpp:27-30,149`: 既定値、整数変換、最小値 clamp、読み取り時点。
- `metal/src/engine/stream.cpp:307-333,464-482`: worker の生成と job 処理。
- `metal/src/engine/window.cpp:435-457,1143,1254-1329`: Metal Window における streaming 選択と arena 作成。
- `metal/src/engine/window.cpp:642-644`, `metal/src/engine/stream.cpp:803-821`: ログと統計。
- `docs/MAC.md:145-157`: M4 の I/O threads に関する測定記述。
