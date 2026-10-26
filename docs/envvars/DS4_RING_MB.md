# `DS4_RING_MB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 専用エンジン `strata-dsv41` の chunked prompt 経路で、GPU に確保する expert ストリーミング ring の概算サイズを MiB 単位で指定します。CPU lane に残った expert をこの ring にコピーし、複数 batch に分けて計算します。値は ring の byte 数そのものではなく、slot 数の算出に使う目標 MiB です。

## 値と判定

`alloc_chunks()` が各 device の `stride > 0` の場合に `getenv()` で設定有無を確認します。未設定なら `ring_mb_auto()` の値を使い、設定済みなら `std::atoi()` の結果を `size_t` に変換して使います。

| 環境変数の状態 | `mb` の値 | 結果 |
|---|---:|---|
| 未設定 | 自動判定で `16` または `400` | 自動判定した目標サイズから slot 数を算出 |
| 整数として読める文字列 | `atoi` の整数結果 | その値から slot 数を算出 |
| 空文字、整数変換できない文字列 | `0` | 自動判定には戻らず、最低 `Chunk::kParts`（4）slot を確保 |

`atoi` は文字列全体の厳密な検証に使われていません。先頭の空白と符号の後にある数字列を読み、後続文字は値の判定に使いません。そのため `128MiB` は `128` として扱われます。負値や `int` の範囲を超える値に対する明示的な検査・clamp はありません。負値は符号付き整数から `size_t` への変換後に計算されるため、意図した MiB 指定として扱える値域ではありません。`atoi` で表現できない数値の結果はコードで定義していません。

ring slot 数は次の式です（`stride` は byte 単位）。

```text
ring_n = max(4, int((mb * 2^20) / stride) / 4 * 4)
```

ここで C++ の実装は `mb << 20` を計算し、まず `stride` で割った値を `int` に変換してから slot 数を 4 の倍数に切り下げます。`mb=0` でも ring は無効化されず、4 slot が下限です。サイズを MiB に合わせて切り上げる処理や、異常値を既定値へ戻す処理はありません。

## 有効になる条件

- 対象は CMake の任意ビルド `STRATA_BUILD_DSV41=ON` で作られる独立実行ファイル `strata-dsv41` です。この CMake option は既定で OFF です。通常の `strata` 実行ファイルの設定ではありません（`CMakeLists.txt:797-811`）。
- モデル初期化で `chunk > 0` のときだけ `alloc_chunks()` が呼ばれます。chunked prompt が無効なら、この変数は読まれません（`src/dsv41/ds4_model.cu:2593-2605`）。chunk の決定には prompt 経路や `--prefill-chunk`、`DS4_CHUNK` など別の条件が関係しますが、この変数自体は chunk の有効化を行いません（同 `:1990-2002`）。
- 各 GPU device の non-MTP layer に属する expert の最大 aligned unit size が `stride` です。`stride == 0` なら ring を確保せず、この変数も読まれません（同 `:2933-2941,2971-2975`）。
- この実装は CUDA runtime API を使う `ds4_model.cu` の経路です。CMake は通常の GPU runtime をリンクし、HIP ビルド時の compatibility layer もあり得ますが、この変数を他のエンジンが読む根拠はありません。

## 実行時の詳細

変数はモデル初期化時の `alloc_chunks()` で評価されます。device ごとに ring の stride と slot 数を設定し、`ring_n * stride` byte の device buffer を確保します。chunk buffer の確保に失敗すると初期化側は確保を解放し、chunk サイズを段階的に小さくして再試行します。最終的に chunk が使えない場合、prompt は window 経路に切り替わります（`src/dsv41/ds4_model.cu:2603-2635`）。環境変数の誤値に特化した警告やエラー文はありませんが、buffer 確保失敗の理由はこの一般的な fallback ログに含まれます。

実行時には `ring_n` が先読み・DMA・計算バッチの上限や循環位置に使われます。ring は 4 parts に分かれ、各 slot は copy stream への非同期転送後に計算で使われ、使用完了イベント後に再利用されます（`src/dsv41/ds4_model.cu:537-544,3498-3528,3548-3580,7610-7652`）。したがって値を大きくすると初期化時の GPU 確保量が増え、chunked prompt 中に保持できる streamed expert 数も増えます。性能や生成結果への定量的な影響は、この調査では測定していません。

未設定時は各 device で `ring_mb_auto()` が呼ばれます。GPU に保持できる expert share を `gpu_expert_share()` で推定し、expert byte 数が正で share が `1 / 1.3` 以上なら 16 MiB、それ以外は 400 MiB を選びます。`--verbose` の場合、自動判定ごとに `ds4: staging ring: experts ... -> 16 MB` または `... -> 400 MB` の形式で stderr に出ます。明示値の経路ではこの自動判定ログは出ません（同 `:2884-2912,2971-2975`）。

## 根拠

- `CMakeLists.txt:797-811`: DS4 専用実行ファイルの任意ビルドと option の既定値。
- `src/dsv41/ds4_model.cu:1990-2002,2593-2605`: chunked prompt の決定と `alloc_chunks()` の呼び出し条件。
- `src/dsv41/ds4_model.cu:2884-2912`: 自動サイズ選択、expert share の閾値、verbose ログ。
- `src/dsv41/ds4_model.cu:2933-2941,2971-2975`: device ごとの stride、環境変数 parse、slot 数計算、ring allocation。
- `src/dsv41/ds4_model.cu:3498-3528,3548-3580,7610-7652`: ring slot の copy・compute・再利用。

`docs/DETAILS.md` と関連資料に `DS4_RING_MB` の個別説明や条件付き測定値は見当たりませんでした。ソースコメント中の過去測定は条件・比較の説明が不足しているため、この文書では性能値として採用していません。
