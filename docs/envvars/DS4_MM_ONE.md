# `DS4_MM_ONE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの開始時状態は `main...origin/main` で、未コミット変更はありませんでした。

## 役割

Metal の DeepSeek IQ expert down 行列積で、dispatch の Y 方向を通常の全 tile 数から 1 に制限します。down の `mm_set` 経路だけに作用します。標準状態は変数未設定で、Y グリッドは `ntiles` です。設定すると最初の tile だけを実行する dispatch になり、down 結果の残りの tile はこのカーネルで計算されません。後続の出力コピー自体は通常どおり行われます。

候補一覧 `docs/envvars/000_envvers.md` に名前があります。Strata ソース中の完全一致参照は `metal/src/engine/ds4_finish.cpp:2614` の 1 箇所で、実際に `std::getenv` で読み取っています。

## 値と判定

| 環境変数の状態 | 判定と効果 |
|---|---|
| 未設定 | 条件分岐に入らず、Y グリッドは `ntiles` のまま |
| 設定あり（空文字を含む） | `getenv` が非 null となり、`d.grid[1] = 1` にする |
| 文字列の内容 | parse・比較・数値変換をしない。`0`、`1`、任意の文字列で同じ効果 |

境界値や無効値の概念はありません。設定値はキャッシュされず、down の `mm_set` 呼び出しごとに確認されます。CLI 引数や他の設定値との優先順位は実装されていません。

## 有効になる条件

- `STRATA_METAL` を定義した Metal ビルドであること。Metal の `set_down` は `hbounds != nullptr` のとき `metal_host::iq_set_dn` を先に呼びます（`src/dsv41/ds4_iq.cu:1604-1608`）。CMake は macOS 限定の Metal ビルドを定義し（`metal/CMakeLists.txt:16-18`）、`strata_ds4` に `STRATA_METAL=1` を設定してこの実装を含めます（同:135-142,165-171）。
- `iq_set_dn` から `mm_set(false, ...)` に入り、expert 数・行数が正で、量子化形式や埋め込み幅などの検査を通り、`mm_prepare()` と Metal pipeline の準備が成功すること（`metal/src/engine/ds4_finish.cpp:2476-2484,2637-2643`）。tile 数が 0 の場合は早期 return するため、この変数の読み取りには到達しません（同:2489-2495）。
- `gate_up == false` の down dispatch であること。gate/up 側では分岐条件を満たしません（同:2533-2535,2614）。

Metal host 実装が `false` を返す条件では `set_down` は後続の通常経路へ進みます（`src/dsv41/ds4_iq.cu:1604-1620`）。その場合、この環境変数によるグリッド変更は行われません。CUDA/HIP の通常ビルドにはこの Metal 実装経路がなく、この変数を読む Strata コードは確認できませんでした。

## 実行時の詳細

`mm_set` は tile 一覧を作り、既定で `d.grid[1] = ntiles` を設定します（`metal/src/engine/ds4_finish.cpp:2489-2495,2529-2533`）。`DS4_MM_ONE` が設定されていれば Y 方向を 1 にし、`DS4_MM_DBG` も設定されている場合だけ、stderr に次の形式で down の診断を出します。

```text
dn tile0 %d %d %d ntiles %d x %u rows %d
```

その後 dispatch を実行し、down 経路では計算結果を engine の行バッファへコピーします（同:2614-2632）。Metal カーネルは `tg.y` を tile index として使い、範囲内の tile だけを書き込みます（`metal/src/engine/msl/ds4_mm.metal:89-100,124-130`）。そのため Y グリッドを 1 にすると tile 0 のみが対象です。残りの結果について Strata がこの分岐内でエラーや警告を出す処理はありません。値だけを設定した場合、`DS4_MM_DBG` による追加ログもありません。

`DS4_MM_ONE` の参照は上記の 1 箇所のみです。`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。候補一覧は環境読み取りの証拠ではありませんが、この commit では Metal ソースに直接の読み取りが確認できました。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2476-2495,2529-2535,2614-2643` — `mm_set` の条件、既定グリッド、変数判定、dispatch 後処理、IQ wrapper。
- `metal/src/engine/msl/ds4_mm.metal:89-100,124-130` — down カーネルが Y 座標を tile index として扱い、tile の出力行を書く処理。
- `src/dsv41/ds4_iq.cu:1604-1620` — Metal down 実装の呼び出しと通常経路への fallback。
- `metal/CMakeLists.txt:16-18,135-142,165-171` — macOS 条件と `strata_ds4` の Metal 定義・ソース構成。
