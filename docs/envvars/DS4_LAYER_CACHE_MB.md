# `DS4_LAYER_CACHE_MB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の prompt 処理で layer-major 経路を使うとき、ファイルから読み込んだ expert を後続 chunk が再利用するホスト側 layer cache の上限を MiB 単位で指定します。指定値は各 layer の expert blob 全体で必要な容量を上限とし、実際に確保できる容量が対象 layer の最大 blob 1個分に満たない場合は layer-major 経路自体が使われません。

この変数は `src/dsv41/ds4_model.cu` の本番 CUDA 実装で読み取られます。候補一覧の名前だけでなく、`lm_begin()` の容量計算と呼び出し元、および layer cache を読み書きする flow を確認しました。

## 値と判定

| 状態・値 | 実装上の扱い |
|---|---|
| 未設定 | `lc_bytes` はまず最大 layer の必要容量 `need` になる。その後 `ram_avail()` が有効値を返す場合、state buffer と `kRamMargin` を差し引いた利用可能メモリ以下に制限される。 |
| 設定あり | `std::atoll()` で数値変換し、結果を `size_t` に変換してから `<< 20` し、`need` との小さい方を使う。従って通常の正の整数 `N` は `N MiB` を指定する。 |
| 空文字・数値として読めない文字列 | `atoll` の変換結果は 0 となり、容量は 0。必要な最大 blob 1個分を下回るため layer-major 開始条件を満たさない。 |
| 数字の後ろに文字が続く値 | `atoll` は先頭の数値部分を変換するため、たとえば `128MB` は数値部分の `128` として扱われる。全体一致や単位 suffix の検証はない。 |
| 負数・範囲外の値 | 負数も拒否する検証や下限 clamp はなく、変換後に `size_t` へ cast してシフトする。範囲外入力もエラー扱いしていないため、通常の非負整数以外の容量を前提にしないこと。 |

明示設定時は `ram_avail()` による空き RAM 上限を適用しません（`need` による上限だけ適用）。確保が実際に成功するかは後段の割り当てで決まり、`os::anon_alloc()` に失敗した場合は layer-major を開始しません。

## 有効になる条件

容量指定だけでは layer-major は有効になりません。`lm_begin()` は次の場合に `false` を返します。

- CUDA device が1台でない、または対象 run の chunk 数が2未満。
- その chunk が file streaming の flow 経路でない。
- `DS4_LAYER_MAJOR` が設定され、`atoi()` の結果が 0（`DS4_LAYER_MAJOR` は別の切り替え変数）。
- file expert の再読込量に対する見込みが state buffer の転送量以下、または最大 layer の cache 必要量が 0。
- `DS4_LAYER_CACHE_MB` から決まった容量が最大 blob 1個分より小さい。
- pinned/pageable state buffer または匿名 layer cache の確保に失敗する。

これらの条件を通過すると `c.lm` が true となり、flow の `run_dev_chunks()` が `run_dev_layers()` に切り替わります。従って、値を十分大きくしても単一 device・複数 chunk の該当 prompt 処理以外には効果がありません。

## 実行時の詳細

環境変数は `lm_begin(run)` が呼ばれるたびに `getenv()` で読みます。値は static cache されないため、次の run では変更が読み直されます（実行中の現在の run の容量は開始時に確定します）。`lm_begin()` は prompt run のセットアップ中に呼ばれ、成立時は状態 buffer と layer cache を確保します。

layer-major 順序では一つの layer を chunk ごとに処理します。file から読んだ expert のうち cache slot に入ったものは、後続 chunk の同じ expert 読み出しに再利用されます。cache slot 数は layer ごとに `min(expert 数, lc_bytes / blob stride)` で求められるため、指定容量が全 expert 分に足りなくても、収まる分だけを保持します。layer-major が使えない場合は通常の chunk 経路に進みます。

`o.verbose` または `DS4_FLOW_STATS` が設定されていると、layer-major が動作した run の統計に `again from the layer cache (layer-major, ... GB of RAM)` が含まれます。`DS4_FLOW_STATS` は設定有無のみを確認し、値の内容は判定しません。このログは指定上限ではなく、その run で確保した cache 容量を表示します。

## 文書との照合

調査時点の `docs/DETAILS.md` と `docs/DEEPSEEK41.md` に `DS4_LAYER_CACHE_MB` の直接の説明は見つかりませんでした。したがって容量、適用条件、fallback の説明は現行ソースに基づきます。文書にある性能値はこの変数の効果として確認できないため記載していません。

## 根拠

- `src/dsv41/ds4_model.cu:8084-8128` — layer-major の必要容量、単一 device / 複数 chunk / flow 条件、`DS4_LAYER_CACHE_MB` の変換、空き RAM 制限、最小容量チェックと割り当て。
- `src/dsv41/ds4_model.cu:8261-8269` — run のセットアップ中に `lm_begin()` を呼び、終了時に確保領域を解放する処理。
- `src/dsv41/ds4_model.cu:7611-7638` — flow の初期化と `c.lm` 時の layer-major 実行への切り替え。
- `src/dsv41/ds4_model.cu:3293-3314,3406-3430,7492-7496` — layer cache のヒット・保持、layer-major 順序、および各 chunk の expert 再利用。
- `src/dsv41/ds4_model.cu:8385-8405` — verbose / `DS4_FLOW_STATS` による cache 容量を含む統計ログ。
