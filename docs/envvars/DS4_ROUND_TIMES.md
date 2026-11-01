# `DS4_ROUND_TIMES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 専用実行ファイル `strata-dsv41` の終了時に、decode round の draft・verify・plain step にかかった時間と GPU dispatch 数の集計を stderr に出します。モデル計算の選択や decode 結果を切り替える変数ではありません。集計カウンター自体はこの変数の有無にかかわらず更新されます。

この名前を直接渡す箇所は `src/dsv41/ds4_main.cpp` の `RoundTimes` デストラクター内の二つの `ds4_dbg("DS4_ROUND_TIMES")` 呼び出しだけです。環境読み取りは `src/dsv41/ds4_launch.h` の共通 helper が行います。

## 値と判定

この変数の値は parse されません。Metal build では `std::getenv(name) != nullptr`、つまり設定の有無だけを調べます。空文字を含む任意の設定値が有効です。unset のときは出力しません。CUDA/HIP など Metal 以外の build では `ds4_dbg` が常に `false` を返すため、設定しても出力されません。

| build | unset | 設定あり（空文字を含む） |
|---|---|---|
| Metal | 無効 | 有効 |
| Metal 以外（CUDA/HIP 等） | 無効 | 無効 |

CLI 引数、設定ファイル、別の環境変数との優先順位はありません。

## 有効になる条件

- `STRATA_BUILD_DSV41` で作られる専用ターゲット `strata-dsv41` に限られます。CMake ではこのターゲットの生成は既定で OFF です。
- `STRATA_METAL` が定義された build でのみ `ds4_dbg` が環境を参照します。CUDA/HIP build では同 helper がコンパイル時定数 `false` です。
- プロセス終了時に `RoundTimes::rounds > 0` である必要があります。このカウンターは `round()` が speculative branch（`spec && room > 1 && m.draft_block() > 0`）へ入る時点で増えます。したがって、この branch に一度も入らない実行では設定しても何も出ません。
- 明示的な有効/無効 CLI オプションや他変数による上書きはありません。通常の speculative decode が起きるかは呼び出し側の実行経路・設定に依存します。

## 実行時の詳細

`RoundTimes` は `ds4_main.cpp` の namespace scope にある `g_rt` で、プロセス終了時にデストラクターが呼ばれます。変数のチェックは decode 時ではなく終了時に行われ、helper は `static` cache を使わず `getenv()` を呼びます。したがって Strata 側に起動時の値の cache はありません。

speculative branch では `rounds` が draft 処理の前に増え、成功した draft の経過時間と dispatch 数が加算されます。draft の採用数が 1 以上の場合は verify の成功後に verify の時間・dispatch 数と `spec_rounds` が増えます。plain step は `m.step()` と sample が成功した後に時間・dispatch 数と `steps` が増えます。失敗経路では `round()` が false を返し、呼び出し元が stderr にエラーを出して終了します。すでに `rounds > 0` なら、その後のプロセス終了時に部分集計が出ることがあります。

終了時の出力は `rounds: ...` で始まる行（draft / verify / plain step の合計 ms と平均 ms）と、`dispatches a round: ...` の行です。両方とも stderr に出し、`rounds == 0` なら抑制します。値を指定する場合は `DS4_ROUND_TIMES=1` のように設定しますが、`1` という数値自体に特別な意味はありません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal では `getenv(name) != nullptr` で判定し、それ以外の build では常に false。
- `src/dsv41/ds4_main.cpp:185-197` — カウンター、終了時条件、stderr の二行の出力。
- `src/dsv41/ds4_main.cpp:218-273` — speculative round / draft / verify / plain step の計時、dispatch 集計、カウンター加算と失敗時の戻り。
- `src/dsv41/ds4_main.cpp:991,1256,1529-1532` — `round()` の主な呼び出し経路と失敗時の stderr 出力。
- `CMakeLists.txt:906-920` — `strata-dsv41` は独立ターゲットで、`STRATA_BUILD_DSV41` は既定 OFF。
- `docs/DEEPSEEK_MAC.md:95-98` は Mac engine の診断変数を列挙していますが、この変数の記載や追加の動作説明・測定値はありません。本書の挙動説明は上記実装に基づきます。
