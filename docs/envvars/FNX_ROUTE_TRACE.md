# `FNX_ROUTE_TRACE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

ビルド時 opt-in の `strata-split` が、MoE の routed expert 選択を GPU 上で記録する計測用設定です。値 `M` は記録領域の容量を百万 pick 単位で指定します。実際にファイルへ保存するには、別の環境変数 `FNX_ROUTE_TRACE_FILE` に出力先を指定します。

これは通常の `strata` engine 全体を制御する設定ではありません。`src/split/CMakeLists.txt` の説明では `strata-split` は `STRATA_BUILD_SPLIT=ON` で有効にする独立した実行ファイルで、既定ではビルドされず、Linux の CUDA または HIP ビルドに限られます。

## 値と判定

`fnx::env_int()` は `std::getenv()` で取得し、10 進の符号付き整数として文字列全体を `strtoll()` で読みます。先頭の `+` / `-` は許されますが、空文字、空白、数字以外の文字、末尾の余分な文字、`long long` の範囲外はエラーです。未設定時は `0` です。

| 値 | 判定と動作 |
| --- | --- |
| 未設定 | `0`。trace 領域を確保せず、記録しません。 |
| `0` または負の整数 | parse は成功しますが `> 0` 条件を満たさず、記録しません。 |
| 正の整数 `M` | card 0 に `M × 1,000,000` pick 分の容量を割り当てます。明示的な上限 clamp はありません。 |
| 空文字、不正な整数、整数範囲外 | `env_int()` が例外を送出します。 |

`FNX_ROUTE_TRACE` 自体に CLI 引数や設定ファイルによる上書きはありません。`strtoll()` の結果が正数でも、`sfnx` では `FNX_ROUTE_TRACE_FILE` が未設定なら起動時に拒否します。出力先変数は値が空でないことまでは検証せず、設定済みかどうかだけを `getenv() != nullptr` で判定します。

## 有効になる条件

- `strata-split` がビルドされ、実行されている必要があります。CMake は Linux CUDA / HIP のみを対象にし、通常の `strata` build には含めません。
- 値が正数である必要があります。バッファ確保は Engine の構築時に行われ、カード 0 にだけ mapped host memory を割り当てます。
- `sfnx` サーバーでは正数の場合に `FNX_ROUTE_TRACE_FILE` も設定されている必要があります。`split_fnx_run` は同じエンジンの診断用 driver ですが、この起動時パス必須チェックを通りません。ファイル変数が設定されていれば終了処理で trace の保存を試みます。
- 値は Engine 構築時に容量へ反映されます。trace の file path は `sfnx` では各 reply 保存時、`split_fnx_run` では結果保存時に読みます。環境変数を後から変更しても Engine の容量は変わりません。

## 実行時の詳細

Engine は正数 `M` を `M × 1,000,000` に換算し、その数の `unsigned` 要素を保持できる mapped host buffer と、累計 pick 数を持つ device 側のカウンターを確保します。FFN の router が top-10 expert を選んだ後、各 layer の routed picks を記録 kernel に渡します。記録値は `(layer << 16) | expert` で、token/row 番号は含みません。GPU thread が atomic increment で記録位置を取るため、layer 内の並びは実行順であり、token 順としては保証されません。

容量を超えても kernel は累計数を増やし続けますが、バッファには容量内の要素だけを書きます。Engine が trace を取得するとき、累計数が容量を超えていれば `FNX_ROUTE_TRACE: <n> picks, room for <cap>: raise it` の例外になります。

`sfnx` は reply ごとに新しく取れた要素を出力します。最初の書き込みは `wb`（既存ファイルを切り詰める）、以後は `ab`（追記）です。ファイルを開けない、または全要素を書けない場合は stderr に `sfnx: FNX_ROUTE_TRACE_FILE: cannot write ...: route tracing stopped after ... picks` を出し、その後の trace 書き込みを停止して server 自体は処理を続けます。trace 容量超過など別の例外は `sfnx` の失敗経路で `ERR ...` と `sfnx: failed: ...` を出し、終了コード 1 で終了します。起動時の値 parse エラーや出力先不足は `sfnx: ...` を stderr に出し、モデルロード前に終了コード 2 となります。

`split_fnx_run` は `FNX_ROUTE_TRACE_FILE` が設定されている場合、全 trace を `wb` で保存します。trace が空、ファイルを開けない、または書き込みに失敗した場合は stderr に `FNX_ROUTE_TRACE_FILE <path>: no trace (FNX_ROUTE_TRACE=M?) or not written` を出して戻り値 1 になります。

## 根拠

- `src/split/src/env.hpp:15-22,33-40`: 整数の全体 parse、未設定時の default、不正値エラー。
- `src/split/src/engine.cu:197-205`: 正数判定、百万 pick 単位の容量、card 0 での host buffer と counter の確保。
- `src/split/src/engine.cu:905-915`: router 後に各 layer の picks を記録 kernel に渡す箇所。
- `src/split/src/kernels.cu:1790-1795,1858-1860`: layer/expert の符号化、atomic による位置取得、容量内だけへの書き込み。
- `src/split/src/engine.cu:672-683`: trace の取得と容量超過例外。
- `src/split/tools/sfnx.cpp:514-541,1007-1012,1027-1035,1040-1048,1086-1092`: 出力先の必須確認、reply ごとのファイル保存・失敗時の継続、起動および例外終了の扱い。
- `src/split/tools/fnx_run.cpp:1154-1161`: 診断 driver のファイル保存と失敗時の戻り値。
- `src/split/CMakeLists.txt:1-7,64-67,153-164`: 独立した opt-in build と対象 backend、server / 診断 driver の構成。
