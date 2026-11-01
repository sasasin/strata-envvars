# `DS4_ZC_MAX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal 版 DeepSeek-V4.1 engine の zero-copy weight mapping 数に上限を設定します。`DS4_ZC_MAX` 自体がこの経路を有効化するわけではありません。`DS4_ZC` が設定され、Metal の DS4 実行経路で条件を満たした expert が必要になった場合に、`DS4_ZC_MAX` が新たに作る Metal buffer の数を制限します。

## 値と判定

`Context::zc_map()` は、既に登録済みのメモリ範囲を再利用できるか先に調べ、その後で初めて `DS4_ZC_MAX` を読みます。読み取り値は `std::atoll()` で整数化して `size_t` に変換し、未設定なら `9000` です。文字列全体の検証、空文字の特別扱い、範囲 clamp はありません。

| 値 | 実装上の結果 |
|---|---|
| 未設定 | 上限 `9000`。既存範囲でない要求は、登録済み buffer 数が 9000 以上なら拒否 |
| 空文字 | `atoll("")` は 0 となり、上限 0。既存範囲の再利用はできるが、新規 mapping は拒否 |
| 数字で始まる文字列 | `atoll` が認識する先頭の整数を採用。たとえば `12tail` は 12 |
| 数字に変換できない文字列 | `atoll` の結果 0。新規 mapping は拒否 |
| 負数 | 負の結果を `size_t` に変換するため、大きな unsigned 上限になる（通常の実行では上限に達しない） |

上限判定は `g_zc.size() >= cap` です。既存の mapping に包含される要求はこの判定より前に GPU address を返すため、上限に達した後も再利用できます。上限判定に通った後、Metal buffer の生成に失敗した場合も `0` を返します。設定値の数値範囲外について `atoll` が返す値は C ライブラリの範囲外変換に依存するため、Strata が保証する境界値としては扱えません。

## 有効になる条件

- `STRATA_METAL` でコンパイルされた DS4 engine の expert 経路であること。通常の非 Metal 経路には `zc_try()` の呼び出しがありません。
- `DS4_ZC` が設定されていること。値の内容は検査せず、空文字を含め、存在すれば有効です。未設定なら `zc_try()` は直ちに false を返し、`DS4_ZC_MAX` は参照されません。
- 対象 expert が `MXFP4` format、`l.nm == 1`、かつ `l.vm` が空でないこと。
- 推論 token 数 `T` が 1 であること。`T > 1` のときは通常の slot/residency 判定だけを使います。

これらを満たすとき、既に GPU slot がある expert はそのまま GPU 扱いです。slot がない expert は `zc_try()` を試し、成功すればその行列を GPU 側の expert として dispatch します。失敗すれば既存の CPU lane に残ります。CLI 引数による `DS4_ZC_MAX` 上書きは見つかりません。

## 実行時の詳細

`DS4_ZC_MAX` の値は `Context::zc_map()` 内の function-local `static const size_t cap` に保存されます。最初に新規 mapping 上限を評価する時点で読み取られ、その後は同一プロセス内で環境を書き換えても更新されません。既存範囲の検索で早期 return する場合は cap の初期化自体が起こらないため、最初に新規範囲を調べるまで環境値の読み取りは遅れます。

`zc_map()` は要求範囲を 16 KiB 境界に丸め、既存 mapping が範囲を覆う場合には既存 GPU address を返します。新規 mapping は cap 判定後に `newBufferWithBytesNoCopy` で要求し、失敗時は 0 を返します。任意の residency set が取得できた場合は buffer を追加して commit します。mapping した buffer は `g_zc` に保持されます。

`zc_try()` は3領域を順に map し、どれか一つでも 0 なら false を返します。false はこの箇所ではエラー終了や専用警告ではなく、expert を CPU lane に振り分ける結果になります。前の領域で成功していた mapping は `g_zc` に残り、後続の要求で再利用され得ます。3領域すべて成功すると expert の matrix descriptor を GPU address で設定します。以降の GPU matrix dispatch が失敗した場合は `mv_n()` の失敗経路に渡りますが、これは cap 固有のログや終了処理ではありません。

`DS4_ZC_MAX` の値や cap 到達を直接報告するログは、この読み取り経路にはありません。

## 根拠

- `metal/src/mtl_rt.mm:415-447`: map table、範囲再利用、cap の読み取り・判定、16 KiB 単位の buffer 作成、失敗時の 0、residency set 登録。
- `metal/src/engine/ds4_finish.cpp:595-599`, `metal/include/metal_compat/ds4_metal_host.h:54`: DS4 host bridge から `Context::zc_map()` への委譲。
- `src/dsv41/ds4_model.cu:4470-4493`: `DS4_ZC` の設定有無、format/matrix 条件、3領域 mapping と GPU matrix descriptor の設定。
- `src/dsv41/ds4_model.cu:10487-10523`: `T == 1` でのみ zero-copy を試し、成功 expert は GPU lane、失敗 expert は CPU lane に振り分ける処理。
- `metal/CMakeLists.txt:151-169`: DS4 runtime の Metal target と `STRATA_METAL` compile definition。

候補名のリポジトリ全体検索では、実装読み取りは `metal/src/mtl_rt.mm:432` の一箇所でした。`docs/DETAILS.md` と他の Markdown に `DS4_ZC_MAX` の説明は見つかりませんでした。
